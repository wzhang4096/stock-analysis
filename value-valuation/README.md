# value-valuation

个股/ETF 估值分位诊断 Skill。输入目标代码（及可选月K、季度财务），输出：

- **PE-TTM 多窗口历史分位**（1年/3年/5年/10年/上市以来）+ 20/70 双阈值判定
- **盈利趋势分型**（A 稳定成长 / B 高速成长 / C 强周期 / D 困境负增长）
- **三道关**（防价值陷阱：口径一致性、绝对值趋势、PEG）
- **回测防误用四过滤**（预期增速换挡、Capex-FCF、回购力度、指数β+技术面）
- 最终四档结论：**①确定性低估 / ②低估 / ③合理偏低 / ④博弈区** + 推荐买入排序

## 快速开始

```bash
# 取数
westock quote 00700 --raw > q.json
westock kline 00700 --period month --limit 300 --raw > k.json
westock finance 00700 --type income --limit 20 --raw > f.json

# 单标的核心分析
python3 scripts/pe_percentile.py --price 428.4 --market-cap 3.902e12 --pe-ttm 14.6 --name 腾讯

# 批量（Top20 等）
python3 scripts/pe_percentile.py --batch top20.json
```

## 文件结构

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 触发条件 + 7步执行流程 |
| `references/methodology.md` | 完整方法论（PE口径/窗口/阈值/分型/三道关/四过滤/特殊类型）|
| `references/output-contracts.md` | 输出契约（字段/阈值映射/四档定义/打分表）|
| `scripts/pe_percentile.py` | 核心计算（分位/陷阱检测/分型/三道关/四过滤）|

## 典型结论速查

| 分型 | 分位偏低时 | 分位偏高时 |
|---|---|---|
| A 稳定成长 | 确定性低估（可重仓）| 正常，持有 |
| B 高速成长 | 低估（轻仓看增速）| 偏高，分批减 |
| C 强周期 | 博弈区（等拐点，禁用PE）| 慎入 |
| D 困境负增长 | 不左侧（等净利转正）| 可止盈 |
