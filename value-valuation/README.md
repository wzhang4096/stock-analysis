# value-valuation

个股/ETF/指数估值分位诊断 Skill。输入目标代码（及可选月K、季度财务），输出 PE-TTM 多窗口历史分位、20/70 双阈值判定、盈利趋势分型（A/B/C/D）、三道关（防价值陷阱）、回测防误用四过滤、跨市场多标的综合排名。适用于港股/美股/A股科技股、成长股、周期股、困境股。

## 快速开始

```bash
# 单标的核心分析
python3 scripts/pe_percentile.py --code 00700 --name 腾讯控股

# 多标的批量（传入 JSON，含 price / market_cap / pe_ttm / 财务）
python3 scripts/pe_percentile.py --batch samples/batch.json

# 跨市场排名（westock 抓取 + TTM 重建 + 六维打分 + 双排名）
python3 scripts/multi_market_rank.py --mkt 港股 --top 10
```

## 文件结构

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 7 步执行流程、四档结论、六维打分、排序一致性约束 |
| `references/methodology.md` | 方法论：PE 口径、分型 A/B/C/D、三道关、四过滤、A股PE陷阱、跨市场共识、排序约束 |
| `references/output-contracts.md` | 五段式输出契约、四档定义、六维打分表、字段4 必答 |
| `scripts/pe_percentile.py` | 核心分析器：多窗口分位 + 窗口陷阱 + 口径校验 + 分型 + 三道关 + 四过滤 |
| `scripts/multi_market_rank.py` | 跨市场批量排名（六维打分 + value/growth 双排名）|
| `.gitignore` | 排除 *.pyc / __pycache__ / 本地 json 数据 |

## 核心规则速查

**分型优先级（互斥）**：D（gr1y<0 & slope<0）→ C（CV>0.5）→ B（gr1y>50% 或 CAGR3>40%）→ A
**双阈值**：分位<20%低估 / 20-50%合理偏低 / 50-70%中枢 / 70-90%偏高 / >90%高估
**四过滤**：C1 预期增速 / C2 Capex-FCF / C3 回购 / C4 指数β+技术面
**排序约束**：同池同口径、四过滤不可关、输出双排名（value / growth）、权重变更须声明

> ⚠️ **A股 PE 口径陷阱**：行情接口的 pe_ratio 为静态/预测口径，与 TTM 口径差异可达 80%+，A股必须重建 PE-TTM。

## 局限

分位只是概率工具不是买卖点；历史数据不足时长窗口分位不可编造；财务数据有延迟，以交易所官方为准。
