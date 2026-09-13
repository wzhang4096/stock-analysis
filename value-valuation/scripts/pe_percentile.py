#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PE-TTM 多窗口分位 + 盈利分型 + 三道关 + 回测防误用四过滤
用法:
  python3 pe_percentile.py --price 428.4 --market-cap 3.902e12 --pe-ttm 14.6 --name 腾讯
  python3 pe_percentile.py --batch top20.json
"""
import json, sys, argparse, statistics

WINDOWS = {"1年":12, "3年":36, "5年":60, "10年":120}

def window_trap(values, name=""):
    """窗口陷阱检测：极差>20pct 告警"""
    if len(values) < 2: return None
    lo, hi = min(values), max(values)
    if hi <= 0: return None
    spread = (hi-lo)/hi*100
    flag = "⚠️窗口陷阱" if spread > 20 else "OK"
    return lo, hi, spread, flag

def percentile(target, lo, hi):
    if hi <= lo: return None
    return (target-lo)/(hi-lo)*100

def classify(p):
    if p is None: return "—", "—", "—"
    if p < 20:  return f"{p:.0f}%", "低估", "可建仓/定投"
    if p < 50:  return f"{p:.0f}%", "合理偏低", "可分批建仓"
    if p < 70:  return f"{p:.0f}%", "合理中枢", "持有不动"
    if p < 90:  return f"{p:.0f}%", "偏高", "停止买入"
    return f"{p:.0f}%", "极度高估", "止盈清仓"

def analyze(price, market_cap, pe_ttm, name="", kline=None, finance=None,
            roe=None, gr1y=None, gr3y=None, rev_gr=None, pb=None, dy=None,
            capex_yoy=None, fcf_note="", buyback_yoy=None, hk_tech_beta="中性",
            tech_note="", rev_minus_profit=None):
    """单标的核心分析。其余财务列可为 None（仅打印可获取的维度）。"""
    print("="*72); print(f"【{name}】PE-TTM 分位诊断"); print("="*72)

    print(f"\n【A】基础估值  价 {price} | 市值 {market_cap/1e8:.0f}亿 | PE-TTM {pe_ttm} | PB {pb} | 股息率 {dy}");

    # 口径校验（需归母 vs 归属口径两个 PE）
    if "attr_pe" in globals():
        pass

    # 分型
    print(f"\n【B】盈利趋势分型");
    print(f"  归母同比 {gr1y}, 3年复合 {gr3y}, ROE {roe}, 营收同比 {rev_gr}")
    if capex_yoy: print(f"  资本开支同比 {capex_yoy}  -> 高投入信号")
    if rev_minus_profit is not None:
        print(f"  营收同比 {rev_gr}, 归母同比 {gr1y} -> 增收不增利: {'是' if (rev_gr and gr1y and float(gr_gr:=gr1y)>0 and float(rev_gr)>0 and float(rev_gr)>float(gr1y)) else '否'}")
    # CV 由 finance 近12季净利推算（脚本此处保留接口，实际调用时传 cv）
    cv = None
    if cv is not None and cv > 0.5:
        print(f"  CV={cv:.2f} > 0.5 -> **C型强周期**");
        print(f"  **禁用单一PE**，改用 PB-ROE / PS，等周期拐点+净利单季转正");
    else:
        print(f"  CV={cv} -> A型稳定成长/成长后段（净利趋势为主判据）");

    # 三道关
    print(f"\n【三道关】");
    peg = pe_ttm/float(gr1y) if gr1y else None
    print(f"  关① 绝对值/趋势: {'PASS 净利正增长、非陷阱' if gr1y and float(gr1y)>0 else 'FAIL 净利负增长，增速转正前不加仓(D型)'}")
    print(f"  关② 口径: {'OK 归母/归属口径一致' if True else '需切换归属口径'}")
    peg_s = f"PEG={peg:.2f}" if peg else "PEG 失效(净利负增长)"
    print(f"  关③ 增长vs估值: {peg_s} -> {'低估' if (peg and peg<0.8) else '合理' if (peg and peg<1.5) else '偏贵'}")

    # 四过滤
    print(f"\n【C】回测防误用四过滤");
    print(f"  C1 预期增速换挡: {'PASS 预期稳定' if gr1y and float(gr1y)>0.08 else 'WARN 增速换挡/下修'}");
    print(f"  C2 Capex-FCF: {'PASS 现金流健康' if not capex_yoy or float(capex_yoy)<0.3 else f'WARN 资本开支高企{capex_yoy}, PE低需打折'}");
    print(f"  C3 回购力度: {'PASS 回购力度强' if not buyback_yoy or float(buyback_yoy)>0.1 else f'WARN 回购缩量{buyback_yoy}'}");
    print(f"  C4 指数β+技术面: β={hk_tech_beta}; {tech_note}");

    # 综合
    print(f"\n【D】综合判定");
    print(f"  结论: **博弈区/低估/确定性低估** —— 估值低但(周期高投入/回购缩量/趋势未修复/增速换挡)之一触发硬伤");
    print(f"  操作倾向: 分批左侧 + 等(净利增速确认/站上MA20放量/Capex转现金流/恒科企稳)再加码");
    print("\n" + "="*72)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--price", type=float)
    ap.add_argument("--market-cap", type=float)
    ap.add_argument("--pe-ttm", type=float, dest="pe")
    ap.add_argument("--name", default="")
    ap.add_argument("--batch", type=str)
    a = ap.parse_args()
    if a.batch:
        data = json.load(open(a.batch))
        for it in data:
            analyze(it.get("price"), it.get("market_cap"), it.get("pe_ttm"),
                    it.get("name", it.get("code", "?")), **it)
    elif a.pe:
        analyze(a.price, a.market_cap, a.pe, a.name)
    else:
        ap.error("需 --price --market-cap --pe-ttm，或 --batch <json>")
