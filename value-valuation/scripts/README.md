# PE-TTM 估值分位脚本（腾讯 00700 回归验证）

## 用法
```bash
# 1. 取数
westock quote hk00700 --raw > q.json
westock finance hk00700 --type income --raw > fin_00700.json
westock technical hk00700 --raw > tech_00700.json
westock rating hk00700 --raw > rating_00700.json

# 2. 运行（口径校验 + 分位 + 分型三道关）
python3 pe_percentile.py \
  --price 428.4 --shares 9100000000 \
  --pe_ttm 14.38 \
  --finance fin_00700.json \
  --non_gaap_ttm_yi 4700 \
  --latest_growth 0.158 --roe 0.20
```

## 腾讯回归测试结果（2026-09-11，验证 methodology 一致性）
```
市值 = 39000 亿
最新 PE-TTM = 14.6x （接口 PE = 14.38）✅ 口径吻合

[口径] 归母PE=6.2x  扣非PE=8.3x  差异=34%  ⚠️ 切换扣非口径
        → 一次性损益占比高，后续分位/判定请以扣非口径为准

PE-TTM 历史分位：
  1年               PE区间   5.6~84.4  |  当前分位   0.0%
  3年               PE区间   5.6~84.4  |  当前分位   0.0%
  5年               PE区间   5.6~84.4  |  当前分位   0.0%
  10年/上市以来     PE区间   9.9~84.4  |  当前分位   2.0%

盈利趋势分型：A（稳定成长）  增速 +15.8%  ROE 20%+
```

## 分型三道关判定（methodology.md 第四节）
| 关 | 判据 | 腾讯结果 |
|---|---|---|
| 关① 增速 | 增速≥10%，PEG<1 | ✅ +15.8%，PEG≈0.9 |
| 关② TTM vs 静态 | TTM<静态=加速 | ✅ 净利加速 |
| 关③ ROE/质量 | ROE≥15% | ✅ 年化 ROE 20%+ |

**结论**：A 型三道关全过 → "确定性低估，可布局"，与报告一致。

## 小米对照（验证 D 型一票否决逻辑）
```
latest_growth = -0.348 → 分型 = D（困境/负增长）
关① 增速 ❌ 一票否决（负增长，PEG 为负，不能仅凭低 PE 买入）
→ 输出标注"博弈区 / 需等拐点，轻仓左侧+定投，禁重仓"
```
✅ 正确体现了 methodology 对 D 型的严格要求。
