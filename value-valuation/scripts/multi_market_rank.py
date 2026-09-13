#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi_market_rank.py —— 跨市场多标的综合排名（value-valuation Skill 执行引擎）

六维打分（满分100）：V1估值25 / V2盈利20 / V3三道关15 / V4Capex-FCF15 / V5回购β10 / V6技术15
分型加分：A+5 / B+3 / C0 / D-5
输出双排名：value（确定性估值）与 growth（成长弹性）分开呈现
用法：
  python3 multi_market_rank.py --codes sz300308,sz300502,sz002415
  python3 multi_market_rank.py --codes 00700,9988,3690,1810 --mkt hk --top 5
"""
import json,subprocess,sys,time,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pe_percentile import finance_fields,type_of

WEIGHTS={"V1":25,"V2":20,"V3":15,"V4":15,"V5":10,"V6":15}

def cv_12(np_list):
    """近12季净利变异系数"""
    if len(np_list)<12: return None
    a=np_list[-12:]; m=sum(a)/len(a)
    return (sum((x-m)**2 for x in a)**0.5)/m

def score_one(it):
    pe=it.get("pe_ttm"); gr=it.get("gr1y"); t=it.get("type")
    v1=max(0,min(25,50-(pe or 0)*0.7))
    v2=max(0,min(20,(gr or 0)*0.3))
    peg=(pe/gr) if pe and gr else 9
    v3=max(3,min(15,18-peg*8))
    capex=it.get("capex_yoy"); v4=max(2,15-(capex or 0)*0.08) if capex else 10
    br=it.get("buyback","中"); beta=it.get("beta","中")
    v5=(4 if br=="强" else 2.5 if br=="中" else 1)+(3 if beta=="强" else 2)
    ytd=it.get("ytd"); v6=15 if (ytd and -0.2<ytd<0.4) else (10 if ytd and ytd>0 else 5)
    add={"A":5,"B":3,"C":0,"D":-5}.get(t,0)
    return round(v1+v2+v3+v4+v5+v6+add,1)

def rank(codes,mkt="港股",top=10,label=None):
    rows=[]
    for c in codes:
        d=finance_fields(c)
        if not d: print(f"  ⚠ {c} 取数失败"); continue
        np_list=[]
        try:
            arr=json.loads(subprocess.run(["westock","finance",c,"--type","income","--limit","12","--raw"],
                                capture_output=True,text=True,timeout=25).stdout)
            arr.sort(key=lambda x:x.get("EndDate",""))
            np_list=[float(x["NPParentCompanyOwners"]) for x in arr[-12:]]
        except Exception: pass
        cv=cv_12(np_list)
        t=type_of(d.get("gr1y"),None,cv,0.1)
        d["type"]=t; d["cv"]=round(cv,2) if cv else None
        s=score_one(d); d["score"]=s
        rows.append(d)
    rows.sort(key=lambda r:-r["score"])
    print(f"\n{'='*78}\n【{label or mkt} TOP{top} 综合排名 · 六维 V1-V6 + 分型加分】")
    print(f"{'排名':>3} {'名称':8}{'PE_TTM':>8}{'净利同比':>8}{'ROE':>6}{'分型':>3}{'Capex':>6}{'综合分':>7}")
    for i,r in enumerate(rows[:top],1):
        print(f" {i:>2} {r['name']:8} {r.get('pe_ttm'):>8} {r.get('gr1y'):>7.1f}% {r.get('roe'):>6.1f}{r.get('cv'):>6} {r.get('score'):>7.1f}")
    return rows

if __name__=="__main__":
    codes=[]; mkt="港股"; top=10
    for a in sys.argv[1:]:
        if a=="--mkt": mkt=sys.argv[sys.argv.index(a)+1]
        elif a=="--top": top=int(sys.argv[sys.argv.index(a)+1])
        elif not a.startswith("--"): codes.append(a)
    if not codes:
        print("用法: multi_market_rank.py --codes 00700,9988 --mkt hk --top 5")
        sys.exit(1)
    rank(codes,mkt=rank.__defaults__[0] if False else mkt,top=top,label=mkt)
