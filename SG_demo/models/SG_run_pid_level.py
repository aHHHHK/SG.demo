"""论文图4.7、图4.8：水位设定值阶跃变化的PID闭环仿真。

默认按论文图示使用800 s总时间、100 s时目标水位由0改为-0.3 m。
模型沿用SG_run_pid_qs.py，但蒸汽流量保持435 kg/s。
默认仅对测量值微分，避免设定值冲击；这是待核实假设，不代表论文精确复现。
"""
import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pyomo.environ import SolverFactory, value

from Pid_test import Pid
from SG_run_pid_qs import (
    Q0, build_model, initialise_from_steady,
    solve_checked,
)

STATE_NAMES = ('Vwt', 'P', 'ar', 'Vsd')
TARGET_BEFORE = 0.0
TARGET_AFTER = -0.3


def run_case(solver, steady, gains, args, label):
    model = build_model()
    initialise_from_steady(model, steady)
    unit = 60.0 if args.pid_time_unit == 'minutes' else 1.0
    kp, ti, td = gains
    controller = Pid(kp, kp / (ti * unit), kp * td * unit)
    level0 = value(steady.SG1.Level[0])
    command = Q0
    level = level0
    previous_level = level0
    previous_previous_level = level0
    previous_error = 0.0
    ki, kd = kp / (ti * unit), kp * td * unit
    rows = [(0, 0.0, TARGET_BEFORE, command, Q0)]
    for k in range(args.duration):
        target_delta = TARGET_BEFORE if k < args.step_time else TARGET_AFTER
        target = level0 + target_delta
        # 在区间起点读设定值和上一采样水位，然后执行本区间给水指令。
        if args.derivative_on == 'measurement':
            error = target - level
            correction = (controller.now_val + kp * (error - previous_error) + ki * error
                          - kd * (level - 2 * previous_level + previous_previous_level))
            previous_error = error
            previous_previous_level, previous_level = previous_level, level
        else:
            correction = controller.cmd_pid(level, target)
        command = max(1e-6, min(560.0, Q0 + correction))
        controller.now_val = command - Q0
        # qs不变；水位设定值的阶跃只改变控制器目标。
        for t in model.t:
            model.SG1.qf[t].fix(command)
            model.SG1.qs[t].fix(Q0)
        solve_checked(solver, model, '{} t={} s'.format(label, k + 1))
        last = model.t.last()
        level = value(model.SG1.Level[last])
        rows.append((k + 1, level - level0, target_delta, command, Q0))
        for name in STATE_NAMES:
            getattr(model.SG1, name)[0].fix(value(getattr(model.SG1, name)[last]))
        if (k + 1) % 100 == 0:
            print('{}: {}/{} s'.format(label, k + 1, args.duration), flush=True)
    return np.asarray(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=int, default=800)
    parser.add_argument('--step-time', type=int, default=100)
    parser.add_argument('--pid-time-unit', choices=['minutes', 'seconds'], default='minutes')
    parser.add_argument('--derivative-on', choices=['measurement', 'error'], default='measurement')
    parser.add_argument('--solver', default=r'D:\.conda\torch\Library\bin\ipopt.exe')
    parser.add_argument('--no-show', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.step_time < args.duration:
        parser.error('必须满足 0 <= step-time < duration')
    solver = SolverFactory('ipopt', executable=args.solver)
    solver.options['linear_solver'] = 'mumps'
    solver.options['halt_on_ampl_error'] = 'yes'
    solver.options['tol'] = 1e-8
    steady = build_model(steady=True)
    solve_checked(solver, steady, '435 kg/s稳态', tee=False)
    fraction = (80.0 - 70.0) / 30.0
    optimised = tuple(a + fraction * (b - a) for a, b in
                      zip((87.78, 1.73, 0.43), (135.28, 1.45, 0.37)))
    cases = [('现场参数', (50.0, 1.6, 0.4)), ('优化整定参数', optimised)]
    results = [run_case(solver, steady, gains, args, label)
               for label, gains in cases]
    output = (Path(__file__).resolve().parent / 'SG_run_pid_level_output' /
              '{}_{}s_step{}s_{}'.format(args.pid_time_unit, args.duration, args.step_time, args.derivative_on))
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    for (label, gains), data, colour, basename in zip(
            cases, results, ['tab:blue', 'black'], ['field', 'optimised']):
        with (output / (basename + '.csv')).open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['time_s', 'delta_level_m', 'target_delta_m', 'qf_kg_s', 'qs_kg_s'])
            writer.writerows(data)
        axes[0].plot(data[:, 0], data[:, 1], color=colour, label=label)
        axes[1].plot(data[:, 0], data[:, 3], color=colour, label='qf（{}）'.format(label))
        post = data[data[:, 0] > args.step_time, 1] - TARGET_AFTER
        print('{} KP/TI/TD={} SAE={:.6g}, MSE={:.6g}'.format(
            label, gains, np.abs(post).sum(), np.square(post).mean()))
    axes[0].step(results[0][:, 0], results[0][:, 2], where='pre', color='black',
                 linestyle='--', label='设定值')
    axes[1].plot(results[0][:, 0], results[0][:, 4], color='black',
                 linestyle='--', label='qs')
    axes[0].set(title='水位设定值变化的水位控制结果', ylabel='Level / m')
    axes[1].set(title='水位设定值变化时给水流量与蒸汽流量', ylabel='q / (kg/s)', xlabel='t / s')
    for ax in axes:
        ax.set_xlim(0, args.duration)
        ax.grid(alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(output / 'pid_level_comparison.png', dpi=180)
    print('结果目录:', output)
    if not args.no_show:
        plt.show()
    else:
        plt.close(fig)


if __name__ == '__main__':
    main()
