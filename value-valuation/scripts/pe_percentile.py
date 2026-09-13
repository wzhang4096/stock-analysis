#!/usr/bin/env python3
"""
PE-TTM 历史分位 + 估值诊断脚本（value-valuation Skill）

功能：
  1. 由「季度归母净利」重建 PE-TTM 序列（市值 / 滚动4季净利）
  2. 计算 1y / 3y / 5y / 10y(上市以来) 四档历史分位
  3. 口径校验：归母 vs 扣非，差异>15% 提示切换扣非口径
  4. 盈利趋势分型：A 稳定成长 / B 高速成长 / C 周期 / D 困境负增长
  5. 输出三道关判定 + 20/70 双阈值估值状态

用法：
  # 仅做分位判定（需手动给 TTM 净利）
  python3 pe_percentile.py --price 26.36 --shares 25759352687 --pe_ttm 17.87

  # 从 westock 导出的 JSON 自动重建序列
  westock finance <code> --type income --raw > fin.json
  python3 pe_percentile.py --price <P> --shares <S> \
      --kline kline_month.json --finance fin.json

单位约定（务必统一）：
  - price     : 元/股
  - shares    : 股
  - 净利(JSON) : 元（脚本内部换算为「亿」）
  - 市值      = price * shares，单位「亿」
"""
import argparse
import json
import os
import statistics
from datetime import datetime


def load_quarterly_nps(finance_json):
    """从 westock finance --type income 导出读取 (日期, 归母净利元) 序列，按日期升序。"""
    with open(finance_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = []
    for r in data:
        np_val = r.get("ProfitToShareholders") or r.get("EarningAfterTax")
        if np_val is None:
            continue
        try:
            np_val = float(np_val)
        except (TypeError, ValueError):
            continue
        rows.append((r["EndDate"], np_val))
    rows.sort(key=lambda x: x[0])
    return rows


def ttm_of(seq, i):
    """seq: [(date, np_in_亿), ...]，取 i 及前3期之和。"""
    return sum(seq[j][1] for j in range(max(0, i - 3), i + 1))


def percentile(sorted_series, value):
    """返回 value 在已排序序列中的分位 (0-100)。"""
    n = len(sorted_series)
    if n == 0:
        return None
    below = sum(1 for v in sorted_series if v < value)
    return round(100 * below / n, 1)


def infer_type(latest_growth, roe, np_std_over_mean):
    """盈利趋势分型：A 稳定成长 / B 高速成长 / C 周期 / D 困境负增长。"""
    if latest_growth is None:
        return "A（默认稳定成长，缺增速数据）"
    if latest_growth < 0:
        return "D（困境/负增长）"
    if np_std_over_mean is not None and np_std_over_mean > 0.6:
        return "C（周期型，盈利波动大）"
    if latest_growth >= 0.40:
        return "B（高速成长）"
    return "A（稳定成长）"


def main():
    ap = argparse.ArgumentParser(description="PE-TTM 历史分位 + 三道关估值诊断")
    ap.add_argument("--price", type=float, required=True, help="当前股价（元/股）")
    ap.add_argument("--shares", type=float, required=True, help="总股本（股）")
    ap.add_argument("--pe_ttm", type=float, help="接口/已知 PE-TTM（可选，用于口径校验）")
    ap.add_argument("--net_profit_ttm_yi", type=float, help="滚动4季归母净利（亿，直接给定则跳过重建）")
    ap.add_argument("--kline", help="月K JSON（westock kline --period month --raw），用于对齐日期")
    ap.add_argument("--finance", help="季度利润表 JSON（westock finance --type income --raw）")
    ap.add_argument("--non_gaap_ttm_yi", type=float, help="滚动4季扣非净利（亿）；提供则优先用扣非口径")
    ap.add_argument("--latest_growth", type=float, help="最新归母净利同比增速（如 0.158 表示+15.8%%），用于分型")
    ap.add_argument("--roe", type=float, help="年化 ROE（如 0.20），用于分型辅助")
    args = ap.parse_args()

    shares_yi = args.shares / 1e8  # 股 → 亿股（市值=price*shares_yi 即「亿元」）
    market_cap_yi = args.price * shares_yi  # 市值（亿）

    # ---- 重建 PE-TTM 序列 ----
    # 优先从 finance 重建完整历史（保证分位有意义）；单值仅作当前点
    series = []  # [(date, pe)]
    if args.finance:
        rows = load_quarterly_nps(args.finance)
        if not rows:
            print("ERROR: finance JSON 中无有效净利数据")
            return 1
        seq = [(d, v / 1e8) for d, v in rows]  # 元 → 亿
        # 计算滚动净利波动（用于周期型判定）
        ttm_vals = [ttm_of(seq, i) for i in range(len(seq))]
        mean_ttm = statistics.mean(ttm_vals)
        std_ttm = statistics.pstdev(ttm_vals) if len(ttm_vals) > 1 else 0
        cv = (std_ttm / mean_ttm) if mean_ttm > 0 else None  # 变异系数
        for i, (d, _) in enumerate(seq):
            ttm_i = ttm_of(seq, i)
            if ttm_i <= 0:
                continue  # 亏损期跳过（PE 无意义）
            series.append((d, market_cap_yi / ttm_i))
        args.net_profit_ttm_yi = ttm_vals[-1]
        pe_now = series[-1][1] if series else None
        print(f"[重建] 季度净利期数={len(rows)}  最新滚动4季净利={ttm_vals[-1]:.1f}亿  "
              f"变异系数CV={cv:.2f}" + ("  → 盈利波动大，倾向周期型" if cv and cv > 0.6 else ""))
    else:
        # 无 finance 历史：退化为单点（分位无法计算，仅输出 PE）
        if not args.net_profit_ttm_yi:
            print("ERROR: 需提供 --finance（推荐）或 --net_profit_ttm_yi")
            return 1
        pe_now = market_cap_yi / args.net_profit_ttm_yi
        series.append(("latest", pe_now))
        print("[提示] 未提供 --finance，仅计算当前 PE，分位将基于单点（无意义）")
        args.net_profit_ttm_yi = None  # 避免下方重复取值

    pe_now = args.pe_ttm or series[-1][1]
    # 口径校验后若切换扣非，以扣非 PE 作为"当前真实 PE"
    if args.non_gaap_ttm_yi:
        pe_now = market_cap_yi / args.non_gaap_ttm_yi
    pes = [p for _, p in series]

    print("=" * 60)
    print(f"市值 = {market_cap_yi:.0f} 亿 = {market_cap_yi/1e4:.2f} 万亿")
    print(f"最新 PE-TTM = {pe_now:.2f}x  （接口 PE = {args.pe_ttm or '未提供'}）")
    print("=" * 60)

    # ---- 口径校验：归母 vs 扣非 ----
    if args.non_gaap_ttm_yi:
        pe_gaap = market_cap_yi / args.net_profit_ttm_yi if args.net_profit_ttm_yi else None
        pe_non = market_cap_yi / args.non_gaap_ttm_yi
        diff = abs(pe_gaap - pe_non) / pe_non if pe_non else 0
        flag = "⚠️ 切换扣非口径" if diff > 0.15 else "✅ 差异可接受"
        print(f"\n[口径] 归母PE={pe_gaap:.2f}x  扣非PE={pe_non:.2f}x  差异={diff*100:.1f}%  {flag}")
        if diff > 0.15:
            print("        → 一次性损益占比高，后续分位/判定请以扣非口径为准")
            pe_now = pe_non

    # ---- 多窗口分位 ----
    n = len(pes)
    windows = [("1年", min(12, n)), ("3年", min(36, n)), ("5年", min(60, n)), ("10年/上市以来", n)]
    print("\nPE-TTM 历史分位：")
    results = {}
    for label, idx in windows:
        sub = sorted(pes[n - idx:])
        pct = percentile(sub, pe_now)
        results[label] = pct
        print(f"  {label:<16} PE区间 {min(sub):6.1f}~{max(sub):6.1f}  |  当前分位 {pct:5.1f}%")

    # 窗口陷阱提示
    vals = [v for v in results.values() if v is not None]
    if vals and (max(vals) - min(vals) > 20):
        print("\n⚠️ 窗口陷阱：各窗口分位极差 > 20pct，存在历史极端值稀释，"
              "请勿跨窗口混用阈值（详见 methodology.md）")

    # ---- 盈利趋势分型 ----
    # 粗略用最新两期滚动净利增速估计（若未显式传 --latest_growth）
    growth = args.latest_growth
    if growth is None and len(series) >= 8:
        ttm_now = market_cap_yi / pe_now if pe_now else 0
        # 用 4 季前的滚动净利做同比近似
        growth = None  # 需 finance 原始序列，此处留待外部传入更准
    atype = infer_type(growth, args.roe, None)
    print(f"\n盈利趋势分型：{atype}")
    if growth is not None:
        print(f"  最新净利同比增速 = {growth*100:+.1f}%")
    if args.roe is not None:
        print(f"  年化 ROE = {args.roe*100:.1f}%")

    # ---- 三道关 + 估值状态 ----
    def status(pct):
        if pct is None:
            return "—"
        if pct < 20:
            return "极度低估"
        if pct < 50:
            return "低估/合理偏低"
        if pct < 70:
            return "合理中枢"
        if pct < 90:
            return "偏高/高估"
        return "极度高估"

    print("\n三道关（差异化，按分型）：")
    if atype.startswith("D"):
        print("  D 型(困境/负增长)：关①增速为一票否决 ❌ → 必须等盈利拐点确认；"
              "关②需站上 MA20/MA60；关③看机构预期差（轻仓左侧+定投，禁重仓）")
    elif atype.startswith("C"):
        print("  C 型(周期)：❌ 禁用单纯 PE 分位 → 改用跨周期正常化盈利 + PB-ROE + 景气位置")
    else:
        print("  A/B 型(成长)：关①增速/PEG → 关②TTM vs 静态 → 关③ROE/现金流")

    print("\n估值判定（20/70 双阈值）：")
    for label, _ in windows:
        print(f"  {label:<16} {results[label]:5.1f}%  →  {status(results[label])}")

    print("\n" + "=" * 60)
    print("提示：完整七段式报告请按 references/output-contracts.md 成文。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
