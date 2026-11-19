"""Adapters for the seven user-confirmed SG experiments.

Original modules are imported, never rewritten. Open-loop experiments retain
their full-horizon objective/initialization. Closed loops retain 1 s collocation
and the original incremental PID / prediction_model construction.
"""
from collections import deque
import copy
import math
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parent / 'models'
sys.path.insert(0, str(SOURCE))

from pyomo.environ import Constraint, SolverFactory, Var, value
import SG_qs
import SG_level
import SG_tem
import SG_run_pid_qs as pid_qs
import SG_run_pid_level as pid_level
import SG_run_nmpc_qs as nmpc_qs
import SG_run_nmpc_level as nmpc_level
from Pid_test import Pid

SOLVER_LOCK = threading.RLock()  # Pyomo NL writer / Ipopt are serialized locally.
PROFILES = {
    'SG_qs': dict(label='蒸汽阶跃 · 开环', family='open', duration=250, step_time=150, flow=250, trim=99),
    'SG_level': dict(label='给水阶跃 · 开环', family='open', duration=200, step_time=150, flow=250, trim=99),
    'SG_tem': dict(label='一次侧温度阶跃 · 开环', family='open', duration=300, step_time=150, flow=250, trim=100),
    'SG_run_pid_qs': dict(label='蒸汽扰动 · PID', family='pid', duration=800, step_time=100, flow=435, trim=0),
    'SG_run_pid_level': dict(label='水位设定 · PID', family='pid', duration=800, step_time=100, flow=435, trim=0),
    'SG_run_nmpc_qs': dict(label='蒸汽扰动 · NMPC', family='nmpc', duration=450, step_time=50, flow=435, trim=0),
    'SG_run_nmpc_level': dict(label='水位设定 · NMPC', family='nmpc', duration=450, step_time=50, flow=435, trim=0),
}


def finite(value_, low, high, name):#输入参数的合法性检查
    if isinstance(value_, bool) or not isinstance(value_, (int, float)) or not math.isfinite(value_) or not low <= value_ <= high:
        raise ValueError(f'{name}: range [{low}, {high}]')
    return float(value_)


def solver_factory():
    executable = Path(sys.executable).parent / 'Library/bin/ipopt.exe'#路径
    solver = SolverFactory('ipopt', executable=str(executable))
    if not solver.available(exception_flag=False):
        raise RuntimeError(f'Ipopt unavailable: {executable}')
    solver.options.update(dict(linear_solver='mumps', halt_on_ampl_error='yes', tol=1e-8, max_iter=1000))
    return solver


def args_for(profile):
    p = PROFILES[profile]
    return SimpleNamespace(duration=200 if profile=='SG_tem' else p['duration'],
        step_time=50 if profile=='SG_tem' else p['step_time'],
        horizon=40, control_horizon=5, control_period=5, r=.1, theta=300,
        ke=15, flow_scale=30, level_band=19.5*.05, qf_min=1e-6, qf_max=530,
        pid_time_unit='minutes', control_structure='cascade', flow_kp=1.2,
        derivative_on='measurement', warmup=100, temperature=299.75,
        temperature_drop=16., temperature_scale='celsius', flow=250.,
        feedwater_temperature=198.8)


def gains_for(variant):#选择PID参数
    if variant == 'field':
        return 50., 1.6, .4
    if variant != 'optimised':
        raise ValueError('variant must be field or optimised')
    return tuple(a+(b-a)/3 for a,b in zip((87.78,1.73,.43),(135.28,1.45,.37)))


class BaselineTwin:
    def __init__(self, profile='SG_run_pid_qs', ratio=.01, variant='optimised'):
        if profile not in PROFILES:#检查实验名称是否存在。
            raise ValueError('Unknown SG profile')
        self.profile, self.spec = profile, PROFILES[profile]#将实验名称和对应的实验参数保存下来
        self.ratio = finite(ratio, -.03, .03, 'ratio')
        if profile == 'SG_tem' and abs(self.ratio) != .01:
            raise ValueError('SG_tem baseline ratio must be ±0.01')
        self.variant = variant
        self.gains = gains_for(variant)
        self.args = args_for(profile)
        self.lock = threading.Lock()
        self.last_access = time.monotonic()
        self.time = 0
        self.time_offset = 99 if profile in ('SG_qs','SG_tem') else 0
        self.qs_reproduction = False
        self.segment_model = False
        self.history = deque(maxlen=12000)
        self.intervened = False
        self.objective = self.slack = self.bias = 0.
        self.latest_prediction = None
        self.previous_steam = self.command = self.spec['flow']
        self.previous_error = 0.
        self.solver = solver_factory()
        with SOLVER_LOCK:
            if self.spec['family'] == 'open':
                self.model = self._open_model()
                pid_qs.solve_checked(self.solver, self.model, profile+' full-horizon baseline')
                self.reference_level = value(self.model.SG1.Level[self.time_offset])
            else:
                self.steady = pid_qs.build_model(steady=True)
                pid_qs.solve_checked(self.solver, self.steady, '435 kg/s baseline steady')
                self.model = pid_qs.build_model()
                pid_qs.initialise_from_steady(self.model, self.steady)
                self.reference_level = value(self.steady.SG1.Level[0])
                if self.spec['family'] == 'nmpc':
                    builder = nmpc_level.build_predictor if profile.endswith('level') else nmpc_qs.prediction_model
                    self.predictor = builder(self.steady, self.args)
        self.level = self.reference_level
        self.previous_level = self.previous_previous_level = self.level
        kp,ti,td = self.gains
        self.controller = Pid(kp,kp/(ti*60),kp*td*60)
        self.flow_controller = Pid(1.2,0,0)
        self.controls = dict(mode='baseline', q_f=self.spec['flow'], q_s=self.spec['flow'],
            t_f=198.8 if self.spec['family']=='open' else 224.55,
            t_av=299.75 if self.spec['family']=='open' else 306.6,
            setpoint=self.reference_level)
        self.history.append(self.snapshot())#将初始时刻的状态保存到历史记录中

    def _open_model(self):
        model_args = SimpleNamespace(duration=self.spec['duration'],step_time=self.spec['step_time'])
        m = (SG_level if self.profile=='SG_level' else SG_qs).make_model(
            self.ratio if self.profile not in ('SG_tem','SG_qs') else 0., model_args)
        if self.profile=='SG_tem':
            # Like SG_qs, load a no-disturbance trajectory. Temperature changes
            # only when the user operates temp; retain the SG_tem heat equation.
            SG_tem.use_log_mean_heat_transfer(m,16.)#改变换热计算方法
        return m

    def _index(self):#确定读取哪个时间点
        if self.segment_model: return 1
        return self.time+self.time_offset if self.spec['family']=='open' else (0 if self.time==0 else 1)

    def snapshot(self):#读取蒸汽发生器状态
        s,t = self.model.SG1,self._index()
        def v(name): return float(value(getattr(s,name)[t]))#相当于动态获取某个 Pyomo 变量在指定时间点的数值。
        def residual(name):
            c=getattr(s,name)[t]
            return float(value(c.body)-value(c.lower))
        state = dict(V_wt=v('Vwt'),P=v('P'),alpha_r=v('ar'),V_sd=v('Vsd'))
        inputs = dict(q_f=v('qf'),q_s=v('qs'),t_f=v('tff'),t_av=v('t_av'))
        return dict(time=self.time,model_time=self.time+self.time_offset,state=state,inputs=inputs,controls=dict(self.controls),
            derived=dict(level=v('Level'),reference_level=self.reference_level,
                delta_level=v('Level')-self.reference_level,
                mixture_height=(v('Vwd')+v('Vsd'))/float(value(s.Ad)),
                liquid_height=v('Vwd')/float(value(s.Ad)),alpha_bar_v=v('av_'),
                V_wd=v('Vwd'),heat_kw=v('Q'),circulation=v('qr'),temperature=v('ts'),
                mass_equation_residual=residual('ode2'),energy_equation_residual=residual('ode3'),
                objective=self.objective,slack=self.slack,bias=self.bias),#计算派生物理量
            provenance=dict(case_type='USER_CONFIRMED_SG_BASELINE',synthetic=False,
                profile=self.profile,variant=self.variant,ratio=self.ratio,
                model='SG_for_SGqinshan_boat_a_0117' if self.spec['family']=='open' else 'SG_for_SGqinshan_boat_final_TP_0115_pid',
                solver='Pyomo DAE / LAGRANGE-RADAU ncp=1 / Ipopt',
                mode='interactive_branch' if self.intervened else 'original_script_baseline',
                duration=self.spec['duration']-self.time_offset,step_time=self.spec['step_time']-self.time_offset,
                action='qs_reproduction' if self.qs_reproduction else 'interactive',
                display_trim=self.spec['trim'],geometry='schematic, not CAD'))

    def _scheduled(self):#决定了仿真过程中每个时刻的基准输入和扰动输入。
        c=dict(self.controls)
        if c['mode']=='manual': return c
        c.update(q_f=self.spec['flow'],q_s=self.spec['flow'],setpoint=self.reference_level)
        if self.spec['family']=='open': return c
        if self.time>=self.spec['step_time']:
            if self.profile.endswith('qs'): c['q_s']=445.
            else: c['setpoint']=self.reference_level-.3
        return c

    def _advance(self, c):
        if self.spec['family']=='open' and c['mode']=='manual':
            # New 1 s collocation segment, initialized by ONLY four states.
            # Never freeze a full past trajectory while retaining its equations.
            old=self.model.SG1; index=self._index()
            builder=SG_level if self.profile=='SG_level' else SG_qs
            m=builder.make_model(0.,SimpleNamespace(duration=1,step_time=1))
            if self.profile=='SG_tem':
                SG_tem.use_log_mean_heat_transfer(m,self.args.temperature_drop)
            for var in m.SG1.component_objects(Var,descend_into=True):
                source=old.find_component(var.local_name)
                if source is not None:
                    for t in var: var[t].set_value(value(source[index]))
            for name in pid_qs.STATE_NAMES:
                getattr(m.SG1,name)[0].fix(value(getattr(old,name)[index]))
            for t in m.t:
                for name,key in [('qf','q_f'),('qs','q_s'),('tff','t_f'),('t_av','t_av')]:
                    getattr(m.SG1,name)[t].fix(c[key])
            pid_qs.solve_checked(self.solver,m,self.profile+' interactive 1 s segment')
            self.model=m;self.segment_model=True;self.time+=1
            return
        if self.spec['family']=='open':#self.spec=PROFILES[profile]
            self.time+=1
            return
        m=self.model
        if self.time>0:
            for name in pid_qs.STATE_NAMES:#导入SG_run_pid_qs里面的变量
                getattr(m.SG1,name)[0].fix(value(getattr(m.SG1,name)[1]))
                #将末端的值给到初值
        if c['mode']=='manual': self.command=c['q_f']
        elif self.spec['family']=='nmpc':
            if self.time%5==0:#每隔五秒优化
                predictor=self.predictor
                for name in pid_qs.STATE_NAMES:
                    getattr(predictor.SG1,name)[0].fix(value(getattr(m.SG1,name)[0]))
                for t in predictor.t: predictor.SG1.qs[t].fix(c['q_s'])
                predictor.previous_u.set_value(self.command)
                predictor.measured_level.set_value(self.level)
                self.bias=0. if self.latest_prediction is None else self.level-self.latest_prediction
                predictor.bias.set_value(self.bias)
                if self.profile.endswith('level'): predictor.target_level.set_value(c['setpoint'])
                pid_qs.solve_checked(self.solver,predictor,'original NMPC optimization')
                self.command=float(value(predictor.u[0]))
                self.latest_prediction=float(value(predictor.SG1.Level[5]))
                self.objective=float(value(predictor.obj));self.slack=float(value(predictor.epsilon))
        elif self.profile.endswith('level'):
            kp,ti,td=self.gains
            error=c['setpoint']-self.level
            correction=(self.controller.now_val+kp*(error-self.previous_error)+kp/(ti*60)*error
                -kp*td*60*(self.level-2*self.previous_level+self.previous_previous_level))
            self.previous_error=error
            self.previous_previous_level,self.previous_level=self.previous_level,self.level
            self.command=max(1e-6,min(560.,435+correction))
            self.controller.now_val=self.command-435
        else:
            correction=self.controller.cmd_pid(self.level,self.reference_level)
            target=c['q_s']+correction
            raw=self.command+self.flow_controller.cmd_pid(self.command,target)
            actual=self.command
            self.command=max(1e-6,min(560.,raw))
            if self.command!=raw:
                self.flow_controller.now_val=self.command-actual
                self.controller.now_val=self.command-c['q_s']
        for t in m.t:
            for name,val in [('qf',self.command),('qs',c['q_s']),('tff',c['t_f']),('t_av',c['t_av'])]:
                getattr(m.SG1,name)[t].fix(val)
        pid_qs.solve_checked(self.solver,m,'SG plant step')
        self.level=float(value(m.SG1.Level[1]));self.time+=1

    def step(self,data):
        if data.get('dt',1)!=1: raise ValueError('原脚本时间步为 1 s，不允许改变')
        if self.time>=self.spec['duration']-self.time_offset: raise ValueError('实验已完成，请重置或切换实验')
        updates=data.get('controls',{})
        if not isinstance(updates,dict) or set(updates)-set(self.controls): raise ValueError('Unknown controls')
        c={**self.controls,**updates}
        if c['mode'] not in ('baseline','manual'): raise ValueError('mode must be baseline or manual')
        if self.intervened and c['mode']=='baseline': raise ValueError('手动干预后需重置才能恢复原脚本基准')
        for name,low,high in [('q_f',1e-6,560),('q_s',1e-6,560),('t_f',150,260),('t_av',290,330),('setpoint',self.reference_level-.5,self.reference_level+.5)]:
            c[name]=finite(c[name],low,high,name)
        if c['mode']=='baseline':
            # UI cannot silently override a reproducibility experiment.
            c=self._scheduled()
        if self.spec['family']=='open' and c['mode']=='baseline':
            # Read the already-solved trajectory; do not deep-copy thousands of
            # Pyomo variables on each playback frame.
            self.time+=1;self.controls=c
            snap=self.snapshot();self.history.append(snap)
            return snap
        # Clone only model/controller mutable state; rollback all on solve failure.
        saved={k:copy.deepcopy(v) for k,v in self.__dict__.items()
               if k not in ('lock','solver','history','steady','args','spec','last_access')}
        with SOLVER_LOCK:
            try:
                self._advance(c)
                self.controls=c
                self.intervened |= c['mode']=='manual'
                snap=self.snapshot()
            except Exception:
                self.__dict__.update(saved)
                raise
        self.history.append(snap)
        return snap

    def action(self,name,ratio=None,temperatures=None):
        """Apply a signed input step now; never restart or schedule it."""
        if self.spec['family']!='open': raise ValueError('这些按钮用于 SG_qs、SG_level（qf）、SG_tem；PID/NMPC 请使用原基准流程')
        if name not in ('qs','qf','level','temp','restore'):
            raise ValueError('Unknown open-loop action')
        selected_ratio=self.ratio if ratio is None else finite(ratio,-.03,.03,'ratio')
        if name=='level':
            raise ValueError('当前为开环模型，level 是输出，不可直接设定；请使用 PID/NMPC 水位设定值实验。本次未改变状态。')
        if name=='restore':
            # Build first; a failed solve must not replace the current session.
            fresh=BaselineTwin(self.profile,self.ratio,self.variant)
            # Keep the lock held by the HTTP handler; never swap it underneath.
            for key,val in fresh.__dict__.items():
                if key!='lock': setattr(self,key,val)
            self.history.clear(); snap=self.snapshot();self.history.append(snap)
            return snap
        current=self.snapshot()
        c={**self.controls,**{key:current['inputs'][key] for key in ('q_f','q_s','t_f','t_av')},'mode':'manual'}
        if name=='qs': c['q_s']=250+520*selected_ratio
        if name=='qf': c['q_f']=250+520*selected_ratio
        if name=='temp':
            temperatures={} if temperatures is None else temperatures
            if not isinstance(temperatures,dict): raise ValueError('temperatures must be an object')
            primary=finite(temperatures.get('t_av',c['t_av']),290,330,'t_av')
            feed=finite(temperatures.get('t_f',c['t_f']),150,260,'t_f')
            c['t_f']=feed
            c['t_av']=primary+feed*selected_ratio
        snap=self.step(dict(dt=1,controls=c))
        self.ratio=selected_ratio
        snap['provenance']['ratio']=selected_ratio
        return snap
