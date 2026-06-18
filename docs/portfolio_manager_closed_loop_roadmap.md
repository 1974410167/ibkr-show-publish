# Portfolio Manager Closed-Loop Roadmap

> 本文档是 `ibkr_show` 项目从单标的 Trade Decision Agent 升级为闭环交易系统的主线锚点。
>
> 后续每个 Portfolio Manager PR 都必须对照本文档验收，避免功能越做越散、偏离长期目标。

---

## 0. 系统最高目标

本系统的最高目标不是预测明天涨跌，而是构建一个长期、可评测、可复盘、可迭代的个人股票交易决策系统。

### 0.1 投资宪法

当前股票账户的长期目标：

- 目标时间：2035 年前。
- 目标规模：账户资产达到 1,500,000 美元。
- 当前本金：不到 90,000 美元。
- 未来允许继续入金，但系统不能把入金视为达成目标的主要来源。
- 核心增长来源：时间、复利、耐心、交易策略、仓位纪律、市场反馈评测。
- 未来十年核心投资主线：AI，也就是人工智能及其基础设施、算力、平台、应用和受益链条。

### 0.2 系统哲学

系统不追求短期胜率最大化，而追求在 2035 年维度下提高账户达到长期目标的概率。

系统不把市场反馈简单解释为“涨了就是对，跌了就是错”。市场反馈是带噪声、延迟、非平稳的评测信号，需要结合收益、回撤、基准、仓位、时间窗口、投资 thesis、AI 主线、组合风险和真实执行情况综合判断。

系统不是训练一个保证赚钱的 AI，而是构建一个市场反馈驱动的闭环交易决策系统。

---

## 1. 总体领域划分

最终系统分为 8 个领域：

1. Investment Constitution，投资宪法。
2. Universe，股票池。
3. Market Watchtower，每日巡检。
4. Auto Decision Orchestrator，自动决策编排。
5. Portfolio Manager，组合经理。
6. Market Evaluation，市场反馈评测。
7. Agent Improvement，Agent 改进闭环。
8. Reporting / Task / UI，任务、报告和前端展示层。

这 8 个领域必须作为长期架构边界保留。即使某个领域第一版功能较简单，也必须落在最终目录和最终概念里，不允许用临时 service 名字糊在 `trade_decision_*` 下。

---

## 2. 最终代码结构

建议新增独立领域包：

```text
ibkr_show_backend/app/domains/portfolio_manager/
  __init__.py

  constitution/
    schemas.py
    repository.py
    service.py
    default_policy.py

  universe/
    schemas.py
    repository.py
    service.py
    sync_holdings.py

  watchtower/
    schemas.py
    scanner.py
    trigger_rules.py
    repository.py
    service.py

  decision_orchestrator/
    schemas.py
    trigger_selector.py
    runner.py
    repository.py
    service.py

  portfolio_review/
    schemas.py
    exposure_analyzer.py
    allocation_analyzer.py
    report_composer.py
    repository.py
    service.py

  evaluation/
    schemas.py
    outcome_evaluator.py
    watchtower_evaluator.py
    portfolio_replay.py
    repository.py
    service.py

  improvement/
    schemas.py
    pattern_detector.py
    recommendation_builder.py
    repository.py
    service.py

  api/
    routes.py
```

前端建议新增：

```text
ibkr_show_frontend/src/views/PortfolioManagerView.vue
ibkr_show_frontend/src/api/portfolioManager.ts
ibkr_show_frontend/src/types/portfolioManager.ts
```

前端页面 Tab：

```text
投资宪法
股票池
每日巡检
自动决策
组合报告
市场评测
系统改进
```

---

## 3. ES Index 规划

建议新增以下 ES index：

```text
ibkr_investment_constitution_v1
ibkr_portfolio_universe_v1
ibkr_portfolio_watchtower_runs_v1
ibkr_portfolio_watchtower_items_v1
ibkr_portfolio_auto_decision_runs_v1
ibkr_portfolio_auto_decision_items_v1
ibkr_portfolio_manager_reports_v1
ibkr_portfolio_evaluation_results_v1
ibkr_portfolio_improvement_reports_v1
```

原则：

- 不要把组合经理数据塞进 trade decision index。
- Trade Decision 仍然只做单标的深度决策。
- Portfolio Manager 负责股票池、扫描、触发、组合报告、评测和改进建议。

---

## 4. 每日最终运行链路

每天系统应按如下顺序自动运行：

```text
1. 读取投资宪法
2. 同步 IBKR 当前持仓到 Universe 的 holding 池
3. 读取 watchlist / candidate / excluded 股票池
4. Watchtower 轻量扫描所有 enabled symbols
5. 生成 watchtower run 和 watchtower items
6. 选出 decision_required symbols
7. Auto Decision Orchestrator 调用现有 Trade Decision Agent
8. 保存 auto decision run / items / decision_id
9. Portfolio Manager 生成组合级报告
10. Evaluation 在未来 1D / 5D / 20D / 60D / 120D / 1Y 自动补评测
11. Improvement 定期生成系统改进建议
```

---

## 5. 领域职责

### 5.1 Investment Constitution

目标：固化最高目标和长期约束。

核心字段：

```text
target_account_value_usd
target_date
starting_capital_usd
primary_theme
primary_theme_description
primary_theme_buckets
allow_future_deposits
deposits_count_as_primary_driver
core_time_horizon_years
risk_constraints
forbidden_behaviors
decision_principles
constitution_version
```

必须表达：

- 2035 年前账户目标 150 万美元。
- 未来入金允许存在，但不能作为主要达成路径。
- 长期复利和仓位纪律优先。
- AI 是未来十年投资主线。
- 中短期波动只作为风险、买点和仓位管理信号，不作为偏离长期主线的充分理由。

---

### 5.2 Universe

目标：定义系统每天要看的股票集合。

股票池类型：

```text
holding：真实持仓
watchlist：主动观察股
candidate：系统候选股
excluded：排除股
```

核心字段：

```text
symbol
display_symbol
name
universe_type
theme_tags
ai_theme_role
priority
enabled
scan_frequency
decision_frequency
max_llm_runs_per_week
source
notes
created_at
updated_at
```

第一版要求：

- 自动把 IBKR 当前持仓同步进 holding 池。
- 支持手动添加观察股，例如 AVGO、NVDA、TSM。
- 支持 excluded，避免系统反复分析不想碰的股票。

---

### 5.3 Market Watchtower

目标：每天轻量扫描持仓和观察池，发现风险和机会。

扫描对象：

```text
holding
watchlist
高优先级 candidate
```

扫描指标：

```text
1D / 5D / 20D return
consecutive_up_days
consecutive_down_days
drawdown_from_20d_high
drawdown_from_60d_high
distance_to_52w_high
distance_to_52w_low
position_weight
unrealized_pnl_pct
gap_to_user_target
gap_to_ai_target
gap_to_ai_max
cash_pressure
event_proximity
ai_theme_alignment
```

输出状态：

```text
normal
watch
attention_required
decision_required
```

典型触发：

- AMD 连跌 5 天。
- INTC 涨幅过大，触发止盈复核。
- AVGO 回调进入观察区，触发建仓决策。
- 单标的仓位超过 max。
- 高波动资产集中度过高。

---

### 5.4 Auto Decision Orchestrator

目标：把 Watchtower 的异常信号转化为 Trade Decision Agent 调用。

职责：

- 判断哪些 symbol 需要跑深度决策。
- 控制每日 LLM 调用上限。
- 防止同一 symbol 重复跑。
- 判断 decision_type：holding_decision / entry_decision。
- 调用现有 Trade Decision Agent。
- 保存 trigger_reason / scan_snapshot / decision_id。

原则：

- 不重新实现交易决策逻辑。
- 不绕过 Trade Decision Agent。
- 不直接下单。
- 不因为触发异常就自动买卖。

---

### 5.5 Portfolio Review

目标：生成组合级报告。

回答：

- 当前组合是否健康？
- 是否偏离 AI 主线？
- 哪些股票超配？
- 哪些股票低配？
- 现金比例是否合理？
- 新增资金应该优先给谁？
- 今日最需要关注哪些标的？
- 哪些标的需要触发交易决策？

输出字段：

```text
portfolio_health_score
ai_theme_exposure
cash_status
concentration_risk
allocation_gaps
top_attention_symbols
action_queue
next_steps
data_limitations
```

原则：

- 组合经理是总指挥。
- Trade Decision Agent 是单标的医生。
- 单标的建议必须服从组合级风险预算和长期目标。

---

### 5.6 Market Evaluation

目标：把未来市场表现结构化为评测信号。

评测对象：

- Watchtower 是否提醒得对。
- Auto Decision 是否触发及时。
- Trade Decision 建议是否有效。
- Portfolio Manager 排序是否有效。
- 观察股买点是否有效。
- 止盈提醒是否过早或过晚。

评测周期：

```text
1D
5D
20D
60D
120D
1Y
```

评测指标：

```text
forward_return
max_drawdown
max_runup
benchmark_relative_return
hit_rate
false_positive
false_negative
missed_opportunity
risk_avoided
trigger_quality
```

原则：

- 市场反馈不是标准答案，而是带噪声的结果信号。
- 不允许简单定义涨了就是对、跌了就是错。
- 必须结合 horizon、仓位、回撤、benchmark、投资 thesis、AI 主线和组合风险综合判断。

---

### 5.7 Agent Improvement

目标：定期生成系统改进建议。

回答：

- 哪些 trigger rule 经常误报？
- 哪些 trigger rule 经常漏报？
- 哪些 action 经常错？
- add_on_pullback 是否过于保守？
- Risk Gate 是否过度保守或过度宽松？
- Portfolio Manager 是否低估某类机会？
- Trade Decision 是否在 AI 主线资产上过早止盈？

输出字段：

```text
improvement_candidates
evidence_summary
affected_versions
suggested_change
expected_impact
requires_human_approval
```

原则：

- 不自动修改系统规则。
- 只生成改进建议。
- 必须经过人工确认后才能进入下一版本。
- 必须记录版本号，避免不知道哪次修改导致表现变化。

---

### 5.8 Reporting / Task / UI

目标：提供任务编排、报告查看和手动触发能力。

要复用现有 AgentTask 模式：

```text
create_task
init_graph_progress
background run
mark_running
mark_completed
mark_failed
```

前端必须有统一入口：

```text
组合经理
```

页面必须能查看：

- 投资宪法。
- 股票池。
- 每日巡检 run。
- 自动决策 run。
- 组合报告。
- 市场评测。
- 系统改进建议。

---

## 6. PR 实施顺序

虽然代码结构要一步到位，但 PR 仍然要分阶段验收。

### Portfolio Manager PR1：建立最终闭环交易系统骨架 + 投资宪法 + 股票池基础

目标：

- 建立最终目录结构。
- 增加投资宪法配置。
- 增加 Universe 股票池。
- 前端新增组合经理入口。
- 不要求自动跑交易决策。

必须完成：

- constitution schema / repository / service / API。
- universe schema / repository / service / API。
- ES index：constitution、universe。
- 前端：投资宪法 Tab、股票池 Tab。
- 后端测试和前端 build。

验收重点：

- 是否建立最终代码结构。
- 是否没有把新逻辑塞进 trade_decision 下。
- 是否固化 2035 / 150 万美元 / AI 主线。
- 是否支持 holding / watchlist / candidate / excluded。

---

### Portfolio Manager PR2：Watchtower 每日巡检

目标：

- 对 Universe 中 enabled symbols 做轻量扫描。
- 生成 watchtower run / items。
- 输出 normal / watch / attention_required / decision_required。

必须完成：

- watchtower schemas / scanner / trigger_rules / repository / service。
- ES index：watchtower_runs、watchtower_items。
- API：运行扫描、查看最近扫描、查看单次扫描详情。
- 前端：每日巡检 Tab。
- 测试：连续涨跌、回撤、仓位超限、观察股触发等。

验收重点：

- 是否轻量扫描，不调用 LLM。
- 是否支持持仓和观察池。
- 是否有明确 trigger_reason。
- 是否不直接给买卖动作。

---

### Portfolio Manager PR3：Auto Decision Orchestrator 自动触发交易决策

目标：

- Watchtower 发现 decision_required 后，自动调用现有 Trade Decision Agent。

必须完成：

- decision_orchestrator schemas / trigger_selector / runner / repository / service。
- ES index：auto_decision_runs、auto_decision_items。
- 支持每日 LLM 调用上限。
- 支持去重，避免重复跑同一 symbol。
- 支持 holding_decision / entry_decision。
- 保存 trigger_reason、scan_snapshot、decision_id。
- 前端：自动决策 Tab。

验收重点：

- 是否复用现有 Trade Decision Agent。
- 是否没有重新实现单股决策逻辑。
- 是否不自动下单。
- 是否完整记录当时触发原因和快照。

---

### Portfolio Manager PR4：Portfolio Review 组合经理报告

目标：

- 生成组合级报告。

必须完成：

- portfolio_review schemas / exposure_analyzer / allocation_analyzer / report_composer / repository / service。
- ES index：portfolio_manager_reports。
- 输出组合健康、AI 主线暴露、集中度、现金状态、低配/超配、重点关注标的、下一步动作队列。
- 前端：组合报告 Tab。

验收重点：

- 是否站在组合层面，而不是重复单股分析。
- 是否读取投资宪法。
- 是否评估 AI 主线暴露。
- 是否把 Trade Decision 结果作为输入，而不是替代它。

---

### Portfolio Manager PR5：Market Evaluation 市场反馈评测

目标：

- 对 Watchtower、Auto Decision、Portfolio Review 做前向评测。

必须完成：

- evaluation schemas / outcome_evaluator / watchtower_evaluator / portfolio_replay / repository / service。
- ES index：portfolio_evaluation_results。
- 支持 1D / 5D / 20D / 60D / 120D / 1Y。
- 评估 forward_return、max_drawdown、benchmark_relative_return、missed_opportunity、risk_avoided。
- 前端：市场评测 Tab。

验收重点：

- 是否避免“涨=对，跌=错”。
- 是否按 horizon 评估。
- 是否区分持仓、观察股、组合报告、自动决策。
- 是否记录 data_limitations。

---

### Portfolio Manager PR6：Agent Improvement 改进建议报告

目标：

- 基于评测结果生成系统改进建议。

必须完成：

- improvement schemas / pattern_detector / recommendation_builder / repository / service。
- ES index：portfolio_improvement_reports。
- 输出 trigger rule、action、risk gate、portfolio rule 的候选改进建议。
- 所有建议必须 requires_human_approval=true。
- 前端：系统改进 Tab。

验收重点：

- 是否只生成建议，不自动改规则。
- 是否引用足够评测证据。
- 是否关联版本号。
- 是否防止根据单次结果过度调整。

---

### Portfolio Manager PR7：Daily Closed-Loop Run 一键闭环任务

目标：

- 提供一个统一任务，串起 Universe Sync → Watchtower → Auto Decision → Portfolio Review。

必须完成：

- 统一 task API。
- 复用 AgentTask 进度。
- 支持后台运行。
- 支持内部 token / 手动触发。
- 支持后续定时任务调用。
- 前端：一键运行、任务进度、历史 run。

验收重点：

- 是否串起闭环。
- 是否失败可降级。
- 是否每一步都有 run_id。
- 是否可追溯。

---

## 7. 每个 PR 的防偏离验收清单

每个 PR 验收时必须回答以下问题：

1. 这个 PR 属于 8 个领域中的哪一个？
2. 它是否服务于 2035 / 150 万美元 / AI 主线？
3. 它是否保持 Trade Decision = 单标的深度决策，Portfolio Manager = 组合级编排？
4. 它是否记录了当时的数据、版本、输入和输出？
5. 它是否为未来市场评测留下了可追踪字段？
6. 它是否避免把市场反馈简单理解为涨跌对错？
7. 它是否避免自动下单？
8. 它是否避免让 Agent 自动修改系统规则？
9. 它是否有测试？
10. 它是否有前端可观察入口？

如果任一答案不清晰，则该 PR 不应继续向后推进。

---

## 8. 后续每次提问建议带上的提示

每次开启新 PR 或验收新 PR 时，建议把本段贴给 ChatGPT / Codex：

```text
请严格遵守 docs/portfolio_manager_closed_loop_roadmap.md。
当前项目目标是构建市场反馈驱动的闭环交易系统，不是普通 AI 股票分析工具。
最高目标是 2035 年前将当前股票账户做到 150 万美元，核心主线是 AI。
请先判断本次任务属于 roadmap 中哪一个领域和哪一个 PR，然后再设计或验收代码。
不得偏离 Trade Decision 单标的决策、Portfolio Manager 组合级编排、Market Evaluation 市场反馈评测、Agent Improvement 人工确认后改进的架构边界。
```

---

## 9. 当前进度

已完成 Trade Decision 主线：

- PR1：Investment Policy 后台配置。
- PR2：Investment Policy 接入交易决策。
- PR3：AI Policy Assessment。
- PR4：Action Calibration。
- PR5：Outcome Replay。
- PR6：Shadow Portfolio Backtest。
- PR7：Execution Alignment。
- PR8：Behavior Profile + Override Annotation。
- PR9：Behavior Profile Reminders 接入交易决策。

下一步进入 Portfolio Manager 主线：

```text
Portfolio Manager PR1：建立最终闭环交易系统骨架 + 投资宪法 + 股票池基础
```

---

## 10. 项目一句话定位

```text
这是一个市场反馈驱动的闭环交易 Agent 系统：每天自动扫描持仓和观察池，触发交易决策，记录当时证据和版本，用未来市场表现评测结果，再通过人工确认的方式迭代策略、风控、仓位和行为提醒，长期服务于 2035 年 150 万美元账户目标和 AI 主线投资框架。
```
