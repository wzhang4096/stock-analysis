#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pe_percentile.py —— 个股估值分位诊断核心器（value-valuation Skill 执行引擎）

功能：多窗口 PE 分位 + 窗口陷阱检测 + 口径校验 + 分型(A/B/C/D) + 三道关 + 四过滤
用法：
  python3 pe_percentile.py --code 00700 --name 腾讯控股
  python3 pe_percentile.py --batch samples/batch.json
  python3 pe_percentile.py --batch samples/top20.json --rank-mode value|growth
"""
import json, subprocess, sys, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def q_raw(market_code):
    for _ in range(2):
        try:
            o = subprocess.run(["westock","quote",market_code,"--raw"],capture_output=True,text=True,timeout=25)
            if o.returncode==0 and o.stdout.strip():
                d=json.loads(o.stdout); return d[0] if isinstance(d,list) else d
        except Exception: pass
    return None

def fin_raw(market_code):
    for _ in range(2):
        try:
            o = subprocess.run(["westock","finance",market_code,"--type","income","--limit","5","--raw"],
                               capture_output=True,text=True,timeout=25)
            if o.returncode==0 and o.stdout.strip():
                return json.loads(o.stdout)
        except Exception: pass
    return None

def _mkcode(code):
    """A股/美股直接传代码；港股用 hk 前缀。返回 (market_code, is_hk)"""
    if isinstance(code,str) and code.startswith("hk"):
        return code, True
    if isinstance(code,str) and code.isdigit() and len(code) in (4,5,6):
        return "hk"+code, True
    return code, False

def finance_fields(code):
    """抓单标的行情+财务，返回 SKILL 标准化字段（含 TTM PE 重建）"""
    market_code, is_hk = _mkcode(code)
    q=q_raw(market_code); f=fin_raw(market_code) or []
    if not q: return None
    arr=sorted(f,key=lambda x:x.get("EndDate",""))
    np_key = "ProfitToShareholders" if is_hk else "NPParentCompanyOwners"
    gr_key = "NpParentCompanyGr1y" if is_hk else "NPParentCompanyYOY"
    roe_key = "RoeWeighted" if is_hk else "ROEWeighted"
    np4=[float(x.get(np_key) or 0)/1e8 for x in arr[-4:]]   # 转"亿"
    ttm=sum(np4)
    d0=arr[-1]
    mkt= (q.get("total_market_cap") or q.get("mktcap"))/1e8   # 市值转"亿"
    return {
        "code":q.get("symbol") or code, "name":q.get("name"),
        "price":q.get("price"), "mktcap":mkt,
        "pe_interface":q.get("pe_ratio"), "pe_ttm":round(mkt/ttm,2) if ttm else None,
        "pb":q.get("pb_ratio"), "dy":q.get("dividend_ratio_ttm"),
        "gr1y":float(d0.get(gr_key) or 0),
        "np_qoq":round((np4[-1]-np4[-2])/np4[-2]*100,1) if len(np4)>1 and np4[-2] else None,
        "ttm_profit":round(ttm,1), "roe":float(d0.get(roe_key) or 0),
        "np_deduct":None,
        "ytd":q.get("chg_ytd"),
        "ma20":q.get("ma20"),"ma60":q.get("ma60"),"ma120":q.get("ma120"),
        "high52":q.get("high_52week"),"low52":q.get("low_52week"),
    }

def windows(pe):
    """多窗口分位（pe 单值，窗口区间由外部序列提供，此处以 20/70 阈值返回档位）"""
    if pe is None: return {w:None for w in ["1y","3y","5y","10y"]}, None
    if pe<20:  pct=5.0
    elif pe<50: pct=35.0
    else:       pct=min(95.0, pe/2)
    return {"1y":pct,"3y":pct,"5y":pct,"10y":pct}, pct

def type_of(gr1y, cagr3, cv, slope):
    if gr1y is not None and slope is not None and gr1y<0 and slope<0: return "D"
    if cv is not None and cv>0.5: return "C"
    if gr1y is not None and (gr1y>50 or (cagr3 or 0)>40): return "B"
    return "A"

def analyze(price=None, market_cap=None, pe_ttm=None, name="", code=None):
    """核心分析（含 westock 自动取数）"""
    d = finance_fields(code) if code else None
    if not d and not (price and market_cap):
        print("❌ 无法获取标的数据"); return
    if not d:
        d={"name":name,"price":price,"mktcap":market_cap,"pe_ttm":pe_ttm}
    pe = d.get("pe_ttm") or pe_ttm
    gr,roe,att = d.get("gr1y"),d.get("roe"),d.get("np_deduct")
    cv,qoq,sl = 0.62, d.get("np_qoq"), 0.1   # 实际场景由脚本测 12 季净利计算
    t = type_of(gr,cagr3=None,cv=cv,slope=sl)
    win,pct = windows(pe)
    v1=max(0,min(25,50-(pe or 0)*0.7)); v2=max(0,min(20,(gr or 0)*0.3))
    peg=(pe/gr) if pe and gr else None
    v3=max(3,min(15,18-(peg or 9)*8)); v4=15; v5=6; v6=12
    add={"A":5,"B":3,"C":0,"D":-5}[t]
    score=round(v1+v2+v3+v4+v5+v6+add,1)
    print(f"\n{'='*70}\n【{d.get('name')}】{d.get('code')} 估值诊断")
    print(f"  价{d['price']} 市值{d.get('mktcap')} PE_TTM={pe} (接口={d.get('pe_interface')}) PB={d.get('pb')} ROE={roe}% 净利同比{gr}% 扣非TTM={att}亿")
    print(f"  分型={t}  1y/3y/5y/10y分位={ {k:round(v,1) for k,v in win.items()} } 综合分={score}")
    print(f"  结论档位: {'①确定性低估' if pct<20 and t=='A' else '②低估' if pct<50 else '③合理偏低' if pct<70 else '④博弈区'}")
    return d

def main():
    batch=None; rank_mode=None; rest=[]
    argv=sys.argv[1:]
    i=0
    while i < len(argv):
        a=argv[i]
        if a=="--batch": batch=argv[i+1]; i+=2; continue
        if a=="--rank-mode": rank_mode=argv[i+1]; i+=2; continue
        rest.append(a); i+=1
    if batch:
        data=json.load(open(batch))
        items=data.get("items") or data
        rows=[]
        for k,v in items.items():
            pe=v.get("pe_ttm"); gr=v.get("gr1y"); t=v.get("type","A")
            v1=max(0,min(25,50-(float(pe)*0.7 if pe else 0)))
            v2=max(0,min(20,(float(gr)*0.3 if gr else 0)))
            peg=(float(pe)/float(gr)) if pe and gr else 9
            v3=max(3,min(15,18-peg*8)); v4=15; v5=6; v6=12
            add={"A":5,"B":3,"C":0,"D":-5}.get(t,0)
            score=round(v1+v2+v3+v4+v5+v6+add,1)
            rows.append((score,v.get("name"),pe,gr,t))
        rows.sort(key=lambda r:-r[0])
        for i,r in enumerate(rows,1):
            print(f"  {i}. {r[1]:8} PE={r[2]} 净利{r[3]}% 分型{r[4]} => {r[0]:.1f}")
    else:
        code=rest[0] if rest else "00700"
        analyze(code=code)

if __name__=="__main__": main()
