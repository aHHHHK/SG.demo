"""论文图2.11：一回路平均温度±1%阶跃的开环水位响应。

沿用SG_qs的0117模型、初值和求解流程。默认先运行100 s初始过渡，
显示区间为0~200 s，显示时间50 s后改变t_av；qf、qs、tff保持不变。
温度百分比默认按模型摄氏温度数值定义，不人为缩放水位响应。
"""
import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pyomo.environ import Constraint, Expression, SolverFactory, Var, log, value

from SG_qs import make_model, solve


def use_log_mean_heat_transfer(m, temperature_drop):
    """局部替换传热式；冷热端均高于二次侧饱和温度。

    固定冷热端温差，平均温度阶跃时两端作相同摄氏温度增量。
    用正温差辅助变量保证Ipopt迭代中的log始终有定义。
    """
    sg = m.SG1
    sg.equ1114.deactivate()
    sg.hot_temperature = Expression(m.t, rule=lambda b, t: b.t_av[t] + temperature_drop /  2)
    sg.cold_temperature = Expression(m.t, rule=lambda b, t: b.t_av[t] - temperature_drop / 2)
    sg.hot_approach = Var(m.t, bounds=(1e-6, None), initialize=40)
    sg.cold_approach = Var(m.t, bounds=(1e-6, None), initialize=10)
    sg.hot_approach_eq = Constraint(
        m.t, rule=lambda b, t: b.hot_approach[t] == b.hot_temperature[t] - b.ts[t])
    sg.cold_approach_eq = Constraint(
        m.t, rule=lambda b, t: b.cold_approach[t] == b.cold_temperature[t] - b.ts[t])
    sg.log_mean_temperature_difference = Expression(
        m.t, rule=lambda b, t: temperature_drop / (log(b.hot_approach[t]) - log(b.cold_approach[t])))
    # 交叉相乘避免求解迭代中两辅助温差暂时相等导致除零。
    sg.log_mean_heat_transfer = Constraint(
        m.t, rule=lambda b, t: b.Q[t] * (log(b.hot_approach[t]) - log(b.cold_approach[t]))
        == b.KK[t] * b.F * temperature_drop)


def one_case(solver, ratio, args):
    # SG_qs的零扰动模型保留作者的初值、目标函数和1 s配置点。
    model_args = argparse.Namespace(
        duration=args.warmup + args.duration,
        step_time=args.warmup + args.step_time)
    m = make_model(0.0, model_args)
    # 模型t_av使用摄氏度。可用kelvin选项检查百分比温标的影响；
    # 论文正文没有明确说明百分比的温标，不能将该选项当成拟合手段。
    reference = args.temperature + (273.15 if args.temperature_scale == 'kelvin' else 0)
    after = args.temperature + 198.8 * ratio
    for t in m.t:
        m.SG1.qf[t].fix(args.flow)
        m.SG1.qs[t].fix(args.flow)
        m.SG1.tff[t].fix(args.feedwater_temperature)
        m.SG1.t_av[t].fix(after if float(t) > model_args.step_time else args.temperature)
    use_log_mean_heat_transfer(m, args.temperature_drop)
    solve(solver, m, '温度阶跃{:+.0%}'.format(ratio))
    level0 = value(m.SG1.Level[m.t.first()])
    full = np.asarray([
        (float(t), value(m.SG1.Level[t]) - level0,
         value(m.SG1.t_av[t]), value(m.SG1.Q[t]), value(m.SG1.P[t]),
         value(m.SG1.qf[t]), value(m.SG1.qs[t]),
         value(m.SG1.hot_temperature[t]), value(m.SG1.cold_temperature[t]),
         value(m.SG1.log_mean_temperature_difference[t])) for t in m.t])
    data = full[full[:, 0] >= args.warmup].copy()
    data[:, 0] -= args.warmup
    data[:, 1] -= data[0, 1]
    return full, data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=int, default=200, help='显示区间长度/s')
    parser.add_argument('--step-time', type=int, default=50, help='显示时间下的阶跃时刻/s')
    parser.add_argument('--warmup', type=int, default=100, help='隐藏的初始过渡时间/s')
    parser.add_argument('--temperature', type=float, default=299.75, help='初始t_av/摄氏度')
    parser.add_argument('--temperature-drop', type=float, default=16.0,
                        help='一回路热端减冷端温度/摄氏度，默认326-293；阶跃时保持不变')
    parser.add_argument('--temperature-scale', choices=['celsius', 'kelvin'], default='celsius')
    parser.add_argument('--flow', type=float, default=250.0, help='固定qf=qs/kg/s，沿用SG_qs工作点')
    parser.add_argument('--feedwater-temperature', type=float, default=198.8)
    parser.add_argument('--solver', default=r'D:\.conda\torch\Library\bin\ipopt.exe')
    parser.add_argument('--no-show', action='store_true')
    args = parser.parse_args()
    if args.duration <= 0 or not 0 <= args.step_time < args.duration or args.warmup < 0:
        parser.error('必须满足duration>0、0<=step-time<duration、warmup>=0')
    if args.flow <= 0 or not np.isfinite([args.temperature, args.flow, args.feedwater_temperature]).all():
        parser.error('输入必须有限且flow>0')
    if not np.isfinite(args.temperature_drop) or args.temperature_drop <= 0:
        parser.error('temperature-drop必须为有限正数')
    solver = SolverFactory('ipopt', executable=args.solver)
    solver.options.update({'linear_solver': 'mumps', 'halt_on_ampl_error': 'yes', 'tol': 1e-8})
    output = Path(__file__).resolve().parent / 'SG_tem_output'
    output.mkdir(exist_ok=True)
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(9, 5.5))
    header = ['time_s', 'delta_level_m', 't_av_degC', 'Q_kW', 'P_MPa', 'qf_kg_s', 'qs_kg_s',
              't_hot_degC', 't_cold_degC', 'log_mean_delta_T_degC']
    for ratio, style in [(-0.01, '-'), (0.01, '--')]:
        full, data = one_case(solver, ratio, args)
        name = '{:+.0f}pct'.format(ratio * 100)
        for suffix, rows in [('_full', full), ('', data)]:
            with (output / (name + suffix + '.csv')).open('w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
        ax.plot(data[:, 0], data[:, 1], color='black', linestyle=style, label=name.replace('pct', '%'))
        post = data[data[:, 0] > args.step_time]
        print('{}: t_av={:.5f} -> {:.5f} °C, ΔLevel范围=[{:.6f}, {:.6f}] m'.format(
            name, args.temperature, post[0, 2], post[:, 1].min(), post[:, 1].max()))
    ax.set(title='一回路冷却剂温度变化的水位输出', xlabel='t / s', ylabel='ΔLevel / m', xlim=(0, args.duration))
    ax.axhline(0, color='0.5', linewidth=0.6)
    ax.set_ylim(-0.3,0.3)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / 'SG_tem_response.png', dpi=180)
    print('结果目录:', output)
    print('说明：沿用SG_qs模型与工作点；求解成功不代表与论文曲线完全一致。')
    if args.no_show:
        plt.close(fig)
    else:
        plt.show()


if __name__ == '__main__':
    main()
