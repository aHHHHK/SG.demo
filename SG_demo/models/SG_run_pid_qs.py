"""论文第4.2节蒸汽扰动的PID对比实验（图4.5、4.6）。

采用作者0115_pid机理模型；不拟合、不平移或缩放仿真曲线。
论文正文写50 s、2%，而图中为100 s、435 -> 445 kg/s；默认按图。
表4.2未标注时间单位，默认TI/TD按分钟解释；可用--pid-time-unit seconds比较。
默认启用作者式流量内环（P=1.2），直接操作qf，未模拟阀门动态。
模型版本、时间单位和内环参数均是复现假设，不代表精确复现。
"""
import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pyomo.environ import (
    ConcreteModel, Objective, SolverFactory, TransformationFactory, Var,
    check_optimal_termination, value,
)
from pyomo.dae import ContinuousSet

from Pid_test import Pid
from SG_for_SGqinshan_boat_final_TP_0115_pid import SG

STATE_NAMES = ('Vwt', 'P', 'ar', 'Vsd')
DERIVATIVE_NAMES = ('dVwt_dt', 'dP_dt', 'dar_dt', 'dVsd_dt')
Q0 = 435.0
Q_AFTER = 445.0
FEED_TEMPERATURE = 224.55
PRIMARY_TEMPERATURE = 306.6
LEVEL_REFERENCE = 19.5


def build_model(steady=False):
    m = ConcreteModel()
    m.t = ContinuousSet(initialize=[0, 1])
    component = SG(m.t)
    m.add_component('SG1', component.SGmodel)
    component.param_of_SG()
    component.var_of_SG()
    component.dvar_of_SG()
    component.SG_model()
    s = m.SG1
    for t in m.t:
        s.qf[t].fix(Q0)
        s.qs[t].fix(Q0)
        s.t_av[t].fix(PRIMARY_TEMPERATURE)
        s.tff[t].fix(FEED_TEMPERATURE)
        s.Level[t].set_value(LEVEL_REFERENCE)
        s.Vwt[t].set_value(82.82)
        s.Vsd[t].set_value(7.677)
        s.P[t].set_value(6.6215)
        s.ar[t].set_value(0.0325)
    m.obj = Objective(expr=1)
    if steady:
        # 零导数且qf=qs时质量守恒恒等成立，避免冗余等式导致自由度计数失败。
        s.ode2.deactivate()
        # 固定水位决定初始水装量；其余状态由零导数与代数方程求出。
        for t in m.t:
            s.Level[t].fix(LEVEL_REFERENCE)
            for name in DERIVATIVE_NAMES:
                getattr(s, name)[t].fix(0)
    else:
        TransformationFactory('dae.collocation').apply_to(
            m, wrt=m.t, nfe=1, ncp=1, scheme='LAGRANGE-RADAU')
    return m


def solve_checked(solver, m, label, tee=False):
    result = solver.solve(m, tee=tee)
    if not check_optimal_termination(result):
        raise RuntimeError('{}求解失败：{} / {}'.format(
            label, result.solver.status, result.solver.termination_condition))


def initialise_from_steady(m, steady):
    # 所有变量仅赋求解初猜；只有四个起点状态固定为初始条件。
    for var in m.SG1.component_objects(Var, descend_into=True):
        source = steady.SG1.find_component(var.local_name)
        if source is None:
            continue
        for index in var:
            datum = source[0] if source.is_indexed() else source
            if datum.value is not None:
                var[index].set_value(value(datum))
    for name in STATE_NAMES:
        getattr(m.SG1, name)[0].fix(value(getattr(steady.SG1, name)[0]))


def run_case(solver, steady, gains, args, label):
    m = build_model()
    initialise_from_steady(m, steady)
    unit = 60.0 if args.pid_time_unit == 'minutes' else 1.0
    kp, ti, td = gains
    # 论文式(4-6)：代码KI=KP*T0/TI，KD=KP*TD/T0；T0=1 s。
    controller = Pid(kp, kp / (ti * unit), kp * td * unit)
    # 导入本函数的旧NMPC程序未传control_structure时保持原来的直接控制。
    cascade = getattr(args, 'control_structure', 'direct') == 'cascade'
    flow_controller = Pid(getattr(args, 'flow_kp', 1.2), 0, 0)
    level0 = value(steady.SG1.Level[0])
    level = level0
    command = Q0
    previous_steam = Q0
    rows = [(0, level0, 0.0, Q0, Q0, value(steady.SG1.P[0]),
             value(steady.SG1.Q[0]))]
    for k in range(args.duration):
        steam = Q0 if k < args.step_time else Q_AFTER
        # 当前区间开始时同步施加蒸汽前馈增量；水位反馈仍在区间末更新。
        # command已包含上一时刻的前馈，不能重复加整个steam。
        if cascade:
            # 外环输出为kg/s修正量；内环比较实际给水与qs+外环输出。
            correction = controller.cmd_pid(level, level0)
            flow_target = steam + correction
            actual_flow = command
            flow_correction = flow_controller.cmd_pid(actual_flow, flow_target)
            # 与作者代码相同：内环累计输出叠加到当前给水，而非阀门开度。
            raw = actual_flow + flow_correction
            command = max(1e-6, min(560.0, raw))
            if command != raw:
                flow_controller.now_val = command - actual_flow
                # 限幅时跟踪实际输出，避免外环继续向不可达方向累积。
                controller.now_val = command - steam
        else:
            command = max(1e-6, min(560.0, command + steam - previous_steam))
        previous_steam = steam
        if not cascade:
            controller.now_val = command - steam
        # 一个采样区间内保持输入；在区间末采样，再计算下一段给水指令。
        for t in m.t:
            m.SG1.qf[t].fix(command)
            m.SG1.qs[t].fix(steam)
        solve_checked(solver, m, '{} t={} s'.format(label, k + 1))
        last = m.t.last()
        level = value(m.SG1.Level[last])
        rows.append((k + 1, level, level - level0, command, steam,
                     value(m.SG1.P[last]), value(m.SG1.Q[last])))
        if not cascade:
            correction = controller.cmd_pid(level, level0)
            raw = steam + correction
            command = max(1e-6, min(560.0, raw))
            controller.now_val = command - steam
        end_states = {name: value(getattr(m.SG1, name)[last])
                      for name in STATE_NAMES}
        for name, end_value in end_states.items():
            getattr(m.SG1, name)[0].fix(end_value)
        if (k + 1) % 100 == 0:
            print('{}: {}/{} s'.format(label, k + 1, args.duration), flush=True)
    return np.asarray(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=int, default=800)
    parser.add_argument('--step-time', type=int, default=100)
    parser.add_argument('--pid-time-unit', choices=['minutes', 'seconds'], default='minutes')
    parser.add_argument('--control-structure', choices=['cascade', 'direct'], default='cascade')
    parser.add_argument('--flow-kp', type=float, default=1.2,
                        help='作者流量内环比例增益，非论文435kg/s工况已确认参数')
    parser.add_argument('--solver', default=r'D:\.conda\torch\Library\bin\ipopt.exe')
    parser.add_argument('--no-show', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.step_time < args.duration:
        parser.error('必须满足 0 <= step-time < duration')
    if not np.isfinite(args.flow_kp) or args.flow_kp <= 0:
        parser.error('flow-kp必须是正的有限数')
    solver = SolverFactory('ipopt', executable=args.solver)
    solver.options['linear_solver'] = 'mumps'
    solver.options['halt_on_ampl_error'] = 'yes'
    solver.options['tol'] = 1e-8
    steady = build_model(steady=True)
    solve_checked(solver, steady, '435 kg/s稳态', tee=True)
    print('稳态:', {name: value(getattr(steady.SG1, name)[0]) for name in STATE_NAMES})
    print('PID时间单位假设:', args.pid_time_unit)
    print('控制结构:', args.control_structure, '流量内环KP:', args.flow_kp)
    # 论文表4.2：在70%与100%之间对80%负荷线性插值。
    fraction = (80.0 - 70.0) / (100.0 - 70.0)
    optimised = tuple(a + fraction * (b - a) for a, b in
                      zip((87.78, 1.73, 0.43), (135.28, 1.45, 0.37)))
    cases = [('现场参数', (50.0, 1.6, 0.4)), ('优化整定参数', optimised)]
    results = [run_case(solver, steady, gains, args, label) for label, gains in cases]
    output = (Path(__file__).resolve().parent / 'SG_run_pid_qs_output' /
              '{}_{}s_step{}s_{}_flowkp{}'.format(
                  args.pid_time_unit, args.duration, args.step_time,
                  args.control_structure, args.flow_kp))
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    for (label, gains), data, colour, basename in zip(
            cases, results, ['tab:blue', 'black'], ['field', 'optimised']):
        with (output / (basename + '.csv')).open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['time_s', 'level_m', 'delta_level_m', 'qf_kg_s',
                             'qs_kg_s', 'pressure_MPa', 'Q_kW'])
            writer.writerows(data)
        axes[0].plot(data[:, 0], data[:, 2], color=colour, label=label)
        axes[1].step(data[:, 0], data[:, 3], where='pre', color=colour,
                     label='qf（{}）'.format(label))
        error = data[data[:, 0] > args.step_time, 2]
        print('{} KP/TI/TD={} SAE={:.6g}, MSE={:.6g}, 水位范围=[{:.6g}, {:.6g}] m'.format(
            label, gains, np.abs(error).sum(), np.square(error).mean(),
            data[:, 2].min(), data[:, 2].max()))
    axes[1].step(results[0][:, 0], results[0][:, 4], where='pre',
                 color='black', linestyle='--', label='qs')
    axes[0].set(title='蒸汽流量阶跃变化的水位控制结果（复现试验，非论文原始曲线）', ylabel='ΔLevel / m')
    axes[1].set(title='给水流量与蒸汽流量', ylabel='q / (kg/s)', xlabel='t / s')
    for ax in axes:
        ax.set_xlim(0, args.duration)
        ax.grid(alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(output / 'pid_qs_comparison.png', dpi=180)
    print('结果目录:', output)
    if not args.no_show:
        plt.show()
    else:
        plt.close(fig)


if __name__ == '__main__':
    main()
