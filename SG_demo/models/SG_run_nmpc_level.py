"""论文4.4.2、图4.12/4.13：水位设定值变化的PID与NMPC机理仿真。

50 s时相对初始稳态水位设定从0变为-0.3 m；qs始终435 kg/s。
沿用已有模型与控制假设，结果未经图像拟合，不代表已经精确复现论文。
"""
import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pyomo.environ import Constraint, Objective, Param, SolverFactory, value

from SG_run_pid_qs import (Q0, STATE_NAMES, build_model,
                           initialise_from_steady, solve_checked)
from SG_run_pid_level import run_case as run_pid
from SG_run_nmpc_qs import prediction_model
from matplotlib.ticker import MultipleLocator

def build_predictor(steady, args):
    m = prediction_model(steady, args)
    m.target_level = Param(initialize=value(steady.SG1.Level[0]), mutable=True)
    # 原qs试验的目标是常数；本试验仅在新模型实例上替换为可更新设定值。
    m.del_component(m.obj)
    m.del_component(m.level_upper)
    m.del_component(m.level_lower)
    m.level_upper = Constraint(m.t, rule=lambda m, t:
        m.SG1.Level[t] <= m.target_level + args.level_band + m.epsilon)
    m.level_lower = Constraint(m.t, rule=lambda m, t:
        m.SG1.Level[t] >= m.target_level - args.level_band - m.epsilon)
    tracking = sum((m.SG1.Level[t] - (m.target_level
                    - (m.target_level - m.measured_level) * math.exp(-float(t) / args.ke)
                    - m.bias)) ** 2 for t in m.t if t > 0)#计算水位误差
    moves = sum(((m.u[j] - (m.previous_u if j == 0 else m.u[j - 1]))
                 / args.flow_scale) ** 2 for j in m.moves)#对流量变化量进行归一化，避免控制量的数值尺度影响优化权重。
    m.obj = Objective(expr=tracking + args.r * moves + args.theta * m.epsilon)
    #r 越大，控制器越不愿意大幅度改变给水流量。
    #theta 越大，控制器越不愿意放宽水位约束。
    return m


def run_nmpc(solver, steady, args, output):
    plant = build_model()
    initialise_from_steady(plant, steady)
    predictor = build_predictor(steady, args)
    level0 = value(steady.SG1.Level[0])
    level, command = level0, Q0#初始给水流量和蒸汽流量，command当前给水流量控制指令。
    predicted = None
    rows = [(0, 0.0, 0.0, Q0, Q0)]
    with (output / 'optimisations.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['time_s', 'target_delta_m', 'command_kg_s', 'objective', 'slack_m', 'bias_m'])
        for k in range(args.duration):
            target_delta = 0.0 if k < args.step_time else -0.3#50s目标水位为-0.3
            if k % args.control_period == 0:#每五秒优化一次
                for name in STATE_NAMES:
                    getattr(predictor.SG1, name)[0].fix(value(getattr(plant.SG1, name)[0]))
                    #它将实际对象模型当前时刻的状态，传递给预测模型。
                predictor.target_level.set_value(level0 + target_delta)#更新预测模型的参数
                predictor.previous_u.set_value(command)
                predictor.measured_level.set_value(level)
                predictor.bias.set_value(0.0 if predicted is None else level - predicted)
                solve_checked(solver, predictor, 'NMPC优化 t={} s'.format(k))
                command = value(predictor.u[0])
                predicted = value(predictor.SG1.Level[args.control_period])
                #保存预测模型在一个控制周期之后的水位预测值。
                writer.writerow((k, target_delta, command, value(predictor.obj),
                                 value(predictor.epsilon), value(predictor.bias)))
                f.flush()
            for t in plant.t:
                plant.SG1.qf[t].fix(command)#给水流量，使用 NMPC 优化得到的控制量。
                plant.SG1.qs[t].fix(Q0)
            solve_checked(solver, plant, 'NMPC对象 t={} s'.format(k + 1))
            level = value(plant.SG1.Level[1])
            rows.append((k + 1, level - level0, target_delta, command, Q0))
            states = {name: value(getattr(plant.SG1, name)[1]) for name in STATE_NAMES}
            for name, datum in states.items():
                getattr(plant.SG1, name)[0].fix(datum)#将当前时刻的状态作为下一秒的初始状态。
            if (k + 1) % 50 == 0:
                print('NMPC: {}/{} s'.format(k + 1, args.duration), flush=True)
    return np.asarray(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--duration', type=int, default=450)
    p.add_argument('--step-time', type=int, default=50)
    p.add_argument('--horizon', type=int, default=40)
    p.add_argument('--control-horizon', type=int, default=5)
    p.add_argument('--control-period', type=int, default=5)
    p.add_argument('--r', type=float, default=0.1)
    p.add_argument('--theta', type=float, default=300)
    p.add_argument('--ke', type=float, default=15)
    p.add_argument('--flow-scale', type=float, default=30)
    p.add_argument('--level-band', type=float, default=19.5 * 0.05)
    p.add_argument('--qf-min', type=float, default=1e-6)
    p.add_argument('--qf-max', type=float, default=530)
    p.add_argument('--pid-time-unit', choices=['minutes', 'seconds'], default='minutes')
    p.add_argument('--derivative-on', choices=['measurement', 'error'], default='measurement')
    p.add_argument('--solver', default=r'D:\.conda\torch\Library\bin\ipopt.exe')
    p.add_argument('--output-tag', default='default')
    p.add_argument('--no-show', action='store_true')
    args = p.parse_args()
    if not (0 <= args.step_time < args.duration and 1 <= args.control_period <= args.horizon
            and args.control_horizon >= 1 and args.flow_scale > 0 and args.ke > 0
            and args.r >= 0 and args.theta > 0 and args.level_band >= 0
            and 0 < args.qf_min < Q0 < args.qf_max):
        p.error('时间、权重、控制域或流量边界不合法')
    if not all(math.isfinite(x) for x in (args.flow_scale, args.ke, args.r, args.theta,
                                          args.level_band, args.qf_min, args.qf_max)):
        p.error('数值参数必须有限')
    if Path(args.output_tag).name != args.output_tag or args.output_tag in ('.', '..'):
        p.error('output-tag必须是单个文件夹名')
    output = Path(__file__).resolve().parent / 'SG_run_nmpc_level_output' / args.output_tag
    output.mkdir(parents=True, exist_ok=True)
    (output / 'settings.json').write_text(json.dumps(vars(args), ensure_ascii=False, indent=2), encoding='utf-8')
    solver = SolverFactory('ipopt', executable=args.solver)
    solver.options.update({'linear_solver': 'mumps', 'halt_on_ampl_error': 'yes',
                           'tol': 1e-8, 'max_iter': 1000})
    steady = build_model(steady=True)
    solve_checked(solver, steady, '初始稳态')
    gains = tuple(a + (b - a) / 3 for a, b in
                  zip((87.78, 1.73, 0.43), (135.28, 1.45, 0.37)))
    pid = run_pid(solver, steady, gains, args, '优化PID')
    save_csv(output / 'pid.csv', pid)
    nmpc = run_nmpc(solver, steady, args, output)
    save_csv(output / 'nmpc.csv', nmpc)
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    for label, data, color in [('PID', pid, 'tab:blue'), ('NMPC', nmpc, 'black')]:
        axes[0].plot(data[:, 0], data[:, 1], color=color, label=label)
        axes[1].step(data[:, 0], data[:, 3], where='pre', color=color, label='qf ({})'.format(label))
        post = data[data[:, 0] > args.step_time]
        err = post[:, 1] - post[:, 2]
        print('{} 水位最低值={:.6g} m，最终值={:.6g} m，SAE={:.6g}，MSE={:.6g}，qf范围=[{:.6g},{:.6g}]'.format(
            label, data[:, 1].min(), data[-1, 1], abs(err).sum(), (err ** 2).mean(),
            data[:, 3].min(), data[:, 3].max()))
    axes[0].step(nmpc[:, 0], nmpc[:, 2], where='pre', color='gray', linestyle='--', label='设定值')
    axes[1].plot(nmpc[:, 0], nmpc[:, 4], color='black', linestyle='--', label='qs')
    axes[0].set(title='水位设定值变化：PID与NMPC（复现试验）', ylabel='ΔLevel / m')
    axes[1].set(title='给水流量与蒸汽流量', ylabel='q / (kg/s)', xlabel='t / s')
    for ax in axes:
        ax.set_xlim(0, args.duration)
        ax.grid(alpha=0.25)
        ax.legend()

    fig.tight_layout()
    fig.savefig(output / 'nmpc_level_comparison.png', dpi=180)
    print('结果目录:', output)
    if args.no_show:
        plt.close(fig)
    else:
        plt.show()


def save_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['time_s', 'delta_level_m', 'target_delta_m', 'qf_kg_s', 'qs_kg_s'])
        w.writerows(rows)


if __name__ == '__main__':
    main()
