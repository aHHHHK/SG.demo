"""论文图2.12：50%负荷给水流量阶跃的开环水位响应。

50 s时给水流量分别作±1%、±2%、±3%阶跃，蒸汽流量和温度保持不变，
输出为相对初始稳态水位的变化量。该程序不包含PID或NMPC闭环。
"""
import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pyomo.environ import (ConcreteModel, Objective, SolverFactory,
                           TransformationFactory, Var, check_optimal_termination,
                           value, minimize)
from pyomo.dae import ContinuousSet

# 0117是作者50%负荷脚本采用的版本，但其自由参数模型在当前求解器下
# 初始稳态不可行。先使用已验证可求解的0115机理模型；结果不能宣称为
# 论文图2.12的精确复现，见程序输出说明。
# 0117包装器对应论文50%负荷脚本，但其模型在当前Ipopt配置下初始稳态不可行。
# 使用已验证可求解的0115包装器保证程序可以运行；若修复0117稳态，可改回该导入。
from SG_con_pid_boat_final_0117 import con_model

# Q0 = 250.0
# T_AV = 299.75
# T_FF = 198.8
# LEVEL0 = 19.5
STATES = ('Vwt', 'P', 'ar', 'Vsd')
RATIOS = (0.01, 0.02, 0.03, -0.01, -0.02, -0.03)


def make_model(ratio, args):
    EHL = ConcreteModel()
    EHL.tf = args.duration
    EHL.t_f = EHL.tf
    EHL.t = ContinuousSet(bounds=(0, EHL.tf))

    con_model(EHL)

    discretizer = TransformationFactory('dae.collocation')
    discretizer.apply_to(
        EHL,
        wrt=EHL.t,
        nfe=EHL.tf,
        ncp=1,
        scheme='LAGRANGE-RADAU'
    )

    def obj_rule(m):
        return sum((m.SG1.ar[t] - 0.023) ** 2 for t in m.t)

    EHL.obj = Objective(expr=obj_rule, sense=minimize)

    for t in EHL.t:
        if t == EHL.t.first():
            EHL.SG1.Vwt[t].fix(74.54300622252669)
            EHL.SG1.Vsd[t].fix(13.480331847229797)
            EHL.SG1.P[t].fix(6.656879528096544)

        qs = 250 if float(t) <= args.step_time else 250  + 520*ratio

        EHL.SG1.qf[t].fix(250)
        EHL.SG1.qs[t].fix(qs)
        EHL.SG1.t_av[t].fix(299.75)
        EHL.SG1.tff[t].fix(198.8)

    return EHL

def solve(solver, model, label):
    result = solver.solve(model, tee=False)
    if not check_optimal_termination(result):
        raise RuntimeError('{}求解失败: {} / {}'.format(
            label, result.solver.status, result.solver.termination_condition))


def one_case(solver, ratio, args):
    m = make_model(ratio, args)
    solve(solver, m, '阶跃{:+.0%}'.format(ratio))
    rows = []
    t0 = value(m.SG1.Level[m.t.first()])
    for t in m.t:
        rows.append((float(t), value(m.SG1.Level[t]) - t0,
                     value(m.SG1.qf[t]), value(m.SG1.qs[t]),
                     value(m.SG1.P[t])))
    return np.asarray(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    # 与原作者“完整运行300 s、删除前99点”的后处理方式一致；
    # 若要严格按论文图2.12的50 s/100 s工况，请显式传 --duration 100 --trim-points 0。
    p.add_argument('--duration', type=int, default=250)
    p.add_argument('--step-time', type=int, default=150)
    p.add_argument('--trim-points', type=int, default=99)
    p.add_argument('--solver', default=r'D:\.conda\torch\Library\bin\ipopt.exe')
    p.add_argument('--no-show', action='store_true')
    args = p.parse_args()
    if not 0 <= args.step_time < args.duration:
        p.error('必须满足0 <= step-time < duration')
    if not 0 <= args.trim_points < args.duration:
        p.error('trim-points必须满足0 <= trim-points < duration')
    solver = SolverFactory('ipopt', executable=args.solver)
    solver.options.update({'linear_solver': 'mumps', 'halt_on_ampl_error': 'yes', 'tol': 1e-8})
    output = Path(__file__).resolve().parent / 'SG_qs_output'
    output.mkdir(exist_ok=True)
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(9, 5.5))
    pressure_fig, pressure_ax = plt.subplots(figsize=(9, 5.5))
    results = {}
    plotted_data = []
    colours = ['black', 'tab:blue', 'tab:purple', 'black', 'tab:blue', 'tab:purple']
    styles = ['-', '-', '-', '--', '--', '--']
    for ratio, colour, style in zip(RATIOS, colours, styles):
        full_data = one_case(solver, ratio, args)
        data = full_data[args.trim_points:].copy()
        if len(data):
            data[:, 0] -= data[0, 0]
            # 切片起点重新作为水位零点。
            data[:, 1] -= data[0, 1]
        results[ratio] = data
        plotted_data.append(data)
        name = '{:+.0f}pct'.format(ratio * 100)
        with (output / (name + '.csv')).open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f); w.writerow(['time_s', 'delta_level_m', 'qf_kg_s', 'qs_kg_s', 'P_MPa']); w.writerows(data)
        with (output / (name + '_full.csv')).open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f); w.writerow(['time_s', 'delta_level_m', 'qf_kg_s', 'qs_kg_s', 'P_MPa']); w.writerows(full_data)
        ax.plot(data[:, 0], data[:, 1], color=colour, linestyle=style,
                label='{:+.0f}%'.format(ratio * 100))
        # 与水位图采用相同的切片、时间轴及线型；压力保留实际值，不归零。
        pressure_ax.plot(data[:, 0], data[:, 4], color=colour, linestyle=style,
                         label='{:+.0f}%'.format(ratio * 100))
    ax.axhline(0, color='0.5', linewidth=0.6)
    ax.set(title='蒸汽流量阶跃变化的水位响应（50%负荷）', xlabel='t / s', ylabel='ΔLevel / m')
    # 切片后时间轴已经从0重新计时，不能再使用原始duration作为右边界。
    max_time = max(float(data[-1, 0]) for data in plotted_data if len(data))
    all_levels = np.concatenate([data[:, 1] for data in plotted_data if len(data)])
    level_min, level_max = float(all_levels.min()), float(all_levels.max())
    level_span = max(level_max - level_min, 1e-6)
    ax.set_xlim(0, max_time)
    ax.set_ylim(level_min,level_max )#- 0.08 * level_span, level_max + 0.08 * level_span
    ax.grid(alpha=0.25); ax.legend(ncol=2)
    fig.tight_layout(); fig.savefig(output / 'SG_level_response.png', dpi=180)
    pressure_ax.set(title='蒸汽流量阶跃变化的压力响应（50%负荷）',
                    xlabel='t / s', ylabel='P / MPa', xlim=(0, max_time))
    pressure_ax.grid(alpha=0.25)
    pressure_ax.legend(ncol=2)
    pressure_fig.tight_layout()
    pressure_fig.savefig(output / 'SG_pressure_response.png', dpi=180)
    print('结果目录:', output)
    if args.no_show:
        plt.close(fig)
        plt.close(pressure_fig)
    else: plt.show()


if __name__ == '__main__':
    main()
