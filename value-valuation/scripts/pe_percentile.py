#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PE-TTM 历史分位诊断脚本
用法:
    python3 pe_percentile.py --price 428.4 --shares 9100000000 --pe_ttm 14.6 \
        --kline k.json --finance f.json
说明:
    --pe_ttm 可直接给定（如从行情接口获取），脚本据此计算各窗口分位；
    若省略 --pe_ttm，则从 --kline (月K: date,close) 与 --finance (按季归母净利) 重建 PE-TTM 序列。
输出: 核心数据 + 1y/3y/5y/10y/上市以来 各窗口分位表 + 双阈值判定 + 三道关诊断 + 四段式报告。
"""
import json, sys, bisect, datetime

def percentile(sorted_vals, x):
    """返回 x 在已升序排序列表中的百分位 (0-100)"""
    if not sorted_vals or x <= sorted_vals[0]:
        return 0.0
    if x >= sorted_vals[-1]:
        return 100.0
    i = bisect.bisect_left(sorted_vals, x)
    if i == len(sorted_vals):
        return 100.0
    v_low, v_high = sorted_vals[i-1], sorted_vals[i]
    if v_high == v_low:
        return (i-1)/len(sorted_vals)*100
    return (i-1 + (x - v_low)/(v_high - v_low)) / len(sorted_vals) * 100

def parse_kline(k):
    """支持 [date, close] 列表 或 {date:[...],close:[...]}"""
    dates, closes = [], []
    if isinstance(k, dict):
        dates = k.get("date") or k.get("dates") or []
        closes = k.get("close") or []
    elif isinstance(k, list) and k and isinstance(k[0], (list, tuple)):
        dates = [d for d, _ in k]; closes = [float(c) for _, c in k]
    return dates, closes

def build_ttm_pe(dates, closes, quarterly_net_profit):
    """按每个月的月末，用最近4个季度归母净利之和重建 PE-TTM 序列 (date, PE)"""
    q = []
    for d, np_ in quarterly_net_profit:
        try:
            q.append((datetime.date.fromisoformat(str(d)), float(np_)))
        except Exception:
            pass
    q.sort(key=lambda x: x[0])
    series = []
    for d, close in zip(dates, closes):
        d = datetime.date.fromisoformat(str(d))
        last4 = [np_ for qd, np_ in q if qd <= d][-4:]
        if len(last4) >= 4 and close > 0:
            ttm_np = sum(last4)
            series.append((d, close, close * 1e9 / ttm_np))  # close 港元/股, 净利亿单位
    return series

def window_percentiles(series, pe_now, windows=(1,3,5,10)):
    """返回 {窗口名: (分位, pe_min, pe_max)}"""
    res = {}
    for w in windows:
        cutoff = series[-1][0] - datetime.timedelta(days=365*w)
        vals = [p for d, _, p in series if d >= cutoff]
        if not vals:
            continue
        svals = sorted(vals)
        pe_min, pe_max = min(svals), max(svals)
        if pe_min == pe_max:
            continue
        pct = percentile(svals, pe_now)
        res[f"{w}年"] = (round(pct, 1), round(pe_min, 1), round(pe_max, 1))
    return res

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    import argparse
    ap = argparse.ArgumentParser(description="PE-TTM 历史分位诊断")
    ap.add_argument("--price", type=float, help="当前股价")
    ap.add_argument("--shares", type=float, help="总股本(股)")
    ap.add_argument("--pe_ttm", type=float, help="PE-TTM(可直接给定或脚本重建)")
    ap.add_argument("--kline", help="月K JSON: [date, close] 列表或 {date:[],close:[]}")
    ap.add_argument("--finance", help="季度归母净利 JSON: [[date, np], ...] 时间升序")
    args = ap.parse_args()

    mkt_cap = None
    if args.price and args.shares:
        mkt_cap = args.price * args.shares / 1e12
    print("=" * 56)
    print("估值分位诊断报告")
    print("=" * 56)
    print(f"当前股价: {args.price}")
    if mkt_cap: print(f"总市值:   {mkt_cap:.2f} 万亿")
    if args.pe_ttm:
        print(f"PE-TTM:   {args.pe_ttm:.1f} 倍")

    if args.kline and args.finance:
        dates, closes = parse_kline(load_json(args.kline))
        qnp = [(d, float(np)) for d, np in load_json(args.finance)]
        series = build_ttm_pe(dates, closes, qnp)
        pe_now = args.pe_ttm or (series[-1][2] if series else None)
        windows = window_percentiles(series, pe_now or 0)
        print(f"重建 PE-TTM(最新月): {pe_now:.1f} 倍")
    else:
        pe_now = args.pe_ttm or 0
        windows = {}

    print("\n【PE-TTM 历史分位（各窗口）】")
    if not windows:
        print("  (未提供历史数据，请传入 --kline 与 --finance 计算)")
    for name, (pct, lo, hi) in windows.items():
        tag = "低估" if pct < 20 else "合理" if pct < 70 else "高估"
        print(f"  {name:8s} 区间 {lo:6.1f}~{hi:6.1f}  | 当前分位 {pct:5.1f}%  [{tag}]")

    pct_now = None
    for w, v in windows.items():
        if "10年" in w: pct_now = v[0]; break
    if pct_now is None:
        for w, v in windows.items():
            if "5年" in w: pct_now = v[0]; break
    if pct_now is not None:
        print(f"\n【阈值判定】当前分位 {pct_now:.1f}% → " +
              ("低估区间，可建仓/定投，越跌越买" if pct_now < 20 else
               "合理偏低区间，可建仓" if pct_now < 50 else
               "合理中枢，持有不动" if pct_now < 70 else
               "偏高/高估区间，分批减仓" if pct_now < 90 else "极度高估，止盈清仓"))

    print("\n【三道关】")
    print("  关1 绝对值: 低分位+低绝对值=真便宜; 低分位+高绝对值=价值陷阱")
    print("  关2 TTM vs 静态: TTM<静态 → 利润加速, 盈利向上")
    print("  关3 增速方向: 增速为正 → 健康; 增速转负 → 下跌中继")
    print("\n【结论】结合分位与三道关综合判断; 周期股改用跨周期平均盈利/PB, 亏损股改用 PB-ROE 框架")
    print("\n" + "=" * 56)
    print("免责声明: 以上为基于公开数据的客观估值分析, 不构成投资建议。")
    print("数据可能有延迟, 请以交易所官方为准, 投资有风险, 决策需谨慎。")
    print("=" * 56)

if __name__ == "__main__":
    main()
