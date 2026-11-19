"""论文4.4.1蒸汽流量扰动：非线性滚动优化与优化PID比较。

真实SG机理方程直接构成预测约束，不拟合论文绘图数据。
默认50 s阶跃435->445 kg/s；图示起点约55 s，可用--step-time调整。
控制/量程假设见同名说明文件；运行成功不等于精确复现论文。
"""
import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pyomo.environ import (ConcreteModel, Constraint, Objective, Param, RangeSet,
                           SolverFactory, TransformationFactory, Var, NonNegativeReals, value)
from pyomo.dae import ContinuousSet

from SG_for_SGqinshan_boat_final_TP_0115_pid import SG
from SG_run_pid_qs import (STATE_NAMES, Q0, Q_AFTER, PRIMARY_TEMPERATURE,
                          FEED_TEMPERATURE, build_model, initialise_from_steady,
                          solve_checked, run_case)


def prediction_model(steady, args):
    m = ConcreteModel()
    m.t = ContinuousSet(bounds=(0, args.horizon))
    component = SG(m.t)
    m.add_component('SG1', component.SGmodel)
    component.param_of_SG()
    component.var_of_SG()
    component.dvar_of_SG()
    component.SG_model()
    TransformationFactory('dae.collocation').apply_to(
        m, wrt=m.t, nfe=args.horizon, ncp=1, scheme='LAGRANGE-RADAU')
    initialise_from_steady(m, steady)
    m.moves = RangeSet(0, args.control_horizon - 1)
    m.u = Var(m.moves, initialize=Q0, bounds=(args.qf_min, args.qf_max))
    m.previous_u = Param(initialize=Q0, mutable=True)
    m.measured_level = Param(initialize=value(steady.SG1.Level[0]), mutable=True)
    m.bias = Param(initialize=0.0, mutable=True)
    m.epsilon = Var(domain=NonNegativeReals, initialize=0.0)
    target = value(steady.SG1.Level[0])

    def block(t):
        # t=1..5共用第一指令，t=6..10共用第二指令；尾段保持末指令。
        return min(max(0, int(math.ceil(float(t) / args.control_period)) - 1),
                   args.control_horizon - 1)

    for t in m.t:
        m.SG1.qf[t].unfix()
        m.SG1.t_av[t].fix(PRIMARY_TEMPERATURE)
        m.SG1.tff[t].fix(FEED_TEMPERATURE)
        m.SG1.qs[t].fix(Q0)
    m.input_hold = Constraint(m.t, rule=lambda m, t: m.SG1.qf[t] == m.u[block(t)])
    # 使用绝对参考水位的5%作安全带，而非对0偏差乘5%。
    m.level_upper = Constraint(m.t, rule=lambda m, t:
        m.SG1.Level[t] <= target + args.level_band + m.epsilon)
    m.level_lower = Constraint(m.t, rule=lambda m, t:
        m.SG1.Level[t] >= target - args.level_band - m.epsilon)
    tracking = sum((m.SG1.Level[t] - (target - (target - m.measured_level)
                    * math.exp(-float(t) / args.ke) - m.bias)) ** 2
                   for t in m.t if t > 0)
    moves = sum(((m.u[j] - (m.previous_u if j == 0 else m.u[j - 1]))
                 / args.flow_scale) ** 2 for j in m.moves)
    m.obj = Objective(expr=tracking + args.r * moves + args.theta * m.epsilon)
    return m


def run_nmpc(solver, steady, args):
    plant = build_model()
    initialise_from_steady(plant, steady)
    predictor = prediction_model(steady, args)
    target = value(steady.SG1.Level[0])
    level = target
    command = Q0
    latest_prediction = None
    rows = [(0, target, 0.0, Q0, Q0, value(steady.SG1.P[0]), value(steady.SG1.Q[0]))]
    diagnostics = []
    for k in range(args.duration):
        steam = Q0 if k < args.step_time else Q_AFTER
        if k % args.control_period == 0:
            for name in STATE_NAMES:
                getattr(predictor.SG1, name)[0].fix(value(getattr(plant.SG1, name)[0]))
            # 只知道当前扰动，预测窗内保持当前qs，不预知未来阶跃。
            for t in predictor.t:
                predictor.SG1.qs[t].fix(steam)
            predictor.previous_u.set_value(command)
            predictor.measured_level.set_value(level)
            predictor.bias.set_value(0.0 if latest_prediction is None else level - latest_prediction)
            solve_checked(solver, predictor, 'NMPC优化 t={} s'.format(k))
            command = value(predictor.u[0])
            latest_prediction = value(predictor.SG1.Level[args.control_period])
            diagnostics.append((k, command, value(predictor.obj), value(predictor.epsilon),
                                value(predictor.bias)))
        for t in plant.t:
            plant.SG1.qf[t].fix(command)
            plant.SG1.qs[t].fix(steam)
        solve_checked(solver, plant, 'NMPC对象 t={} s'.format(k + 1))
        level = value(plant.SG1.Level[plant.t.last()])
        rows.append((k + 1, level, level - target, command, steam,
                     value(plant.SG1.P[1]), value(plant.SG1.Q[1])))
        end = {name: value(getattr(plant.SG1, name)[1]) for name in STATE_NAMES}
        for name, datum in end.items():
            getattr(plant.SG1, name)[0].fix(datum)
        if (k + 1) % 50 == 0:
            print('NMPC: {}/{} s'.format(k + 1, args.duration), flush=True)
    return np.asarray(rows), diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=int, default=450)
    parser.add_argument('--step-time', type=int, default=50)
    parser.add_argument('--horizon', type=int, default=40)
    parser.add_argument('--control-horizon', type=int, default=5)
    parser.add_argument('--control-period', type=int, default=5)
    parser.add_argument('--r', type=float, default=0.1)
    parser.add_argument('--theta', type=float, default=300)
    parser.add_argument('--ke', type=float, default=15)
    parser.add_argument('--flow-scale', type=float, default=30,
                        help='流量增量归一化尺度；1表示直接以kg/s代入R')
    parser.add_argument('--level-band', type=float, default=19.5 * 0.05)
    parser.add_argument('--qf-min', type=float, default=1e-6)
    parser.add_argument('--qf-max', type=float, default=530)
    parser.add_argument('--pid-time-unit', choices=['minutes', 'seconds'], default='minutes')
    parser.add_argument('--solver', default=r'D:\.conda\torch\Library\bin\ipopt.exe')
    parser.add_argument('--output-tag', default='default')
    parser.add_argument('--no-show', action='store_true')
    args = parser.parse_args()
    if not (0 <= args.step_time < args.duration and 1 <= args.control_period <= args.horizon
            and args.control_horizon >= 1 and args.flow_scale > 0 and args.ke > 0
            and args.r >= 0 and args.theta > 0 and args.level_band >= 0
            and 0 < args.qf_min <= Q0 < Q_AFTER <= args.qf_max):
        parser.error('时间、控制域、归一化尺度、权重或流量边界不合法')
    if Path(args.output_tag).name != args.output_tag or args.output_tag in ('.', '..'):
        parser.error('output-tag必须是单个文件夹名称')
    output = Path(__file__).resolve().parent / 'SG_run_nmpc_qs_output' / args.output_tag
    output.mkdir(parents=True, exist_ok=True)
    solver = SolverFactory('ipopt', executable=args.solver)
    solver.options.update({'linear_solver': 'mumps', 'halt_on_ampl_error': 'yes',
                           'tol': 1e-8, 'max_iter': 1000})
    steady = build_model(steady=True)
    solve_checked(solver, steady, '初始稳态')
    gains = tuple(a + (b - a) / 3 for a, b in
                  zip((87.78, 1.73, 0.43), (135.28, 1.45, 0.37)))
    pid = run_case(solver, steady, gains, args, '优化PID')
    save_csv(output / 'pid.csv', pid)
    nmpc, diagnostics = run_nmpc(solver, steady, args)
    save_csv(output / 'nmpc.csv', nmpc)
    with (output / 'optimisations.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['time_s', 'command_kg_s', 'objective', 'slack_m', 'bias_m'])
        w.writerows(diagnostics)
    (output / 'settings.json').write_text(json.dumps(vars(args), ensure_ascii=False, indent=2), encoding='utf-8')
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    for label, data, color in [('PID', pid, 'tab:blue'), ('NMPC', nmpc, 'black')]:
        axes[0].plot(data[:, 0], data[:, 2], color=color, label=label)
        axes[1].step(data[:, 0], data[:, 3], where='pre', color=color, label='qf ({})'.format(label))
        error = data[data[:, 0] > args.step_time, 2]
        print('{} 水位范围=[{:.6g},{:.6g}] m, SAE={:.6g}, MSE={:.6g}'.format(
            label, error.min(), error.max(), abs(error).sum(), (error ** 2).mean()))
    axes[1].step(nmpc[:, 0], nmpc[:, 4], where='pre', color='black', linestyle='--', label='qs')
    axes[0].set(title='蒸汽流量阶跃：PID与NMPC（机理仿真复现试验）', ylabel='ΔLevel / m')
    axes[1].set(title='给水流量与蒸汽流量', ylabel='q / (kg/s)', xlabel='t / s')
    for ax in axes:
        ax.set_xlim(0, args.duration)
        ax.grid(alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(output / 'nmpc_qs_comparison.png', dpi=180)
    print('结果目录:', output)
    if args.no_show:
        plt.close(fig)
    else:
        plt.show()


def save_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['time_s', 'level_m', 'delta_level_m', 'qf_kg_s', 'qs_kg_s', 'pressure_MPa', 'Q_kW'])
        writer.writerows(rows)


if __name__ == '__main__':
    main()
