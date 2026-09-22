# 栖月汇经营探究引擎

## 目录

1. 探究合同
2. 业务形态分类
3. 证据面与质量门
4. 语义建模
5. 三个串行波次
6. 竞争假设与机会评估
7. 方案工程化
8. 数据需求与跨层边界
9. 人工协助契约
10. 分析过程与 Checkpoint
11. 复用节奏
12. 输出模板

## 1. 探究合同

开始观察前冻结：

- `channel/entity`：渠道与具体经营实体；
- `question`：本次要回答的经营问题，不用“看看数据”代替；
- `analysisType`：首次全店基线、周复盘、专题、机制验证或多实体比较；
- `scope/window/cutoff`：商品、客户、关系、订单与时间窗；
- `allowedEvidence`：后台、小程序、AOS 数据产品、本体投影、负责人说明、已批准 DataNeed Receipt；
- `writeBoundary`：默认只读，外部动作另行审批；
- `decisionOwner` 与停止条件。

同一渠道下可能有多个店铺实体；同一品牌也可能同时经营私域微商城、微信小店或其他渠道。不要把渠道、店铺、品牌和主体混成一个 ID。

## 2. 业务形态分类

先分类再选指标：

| 形态 | 典型信号 | 首要问题 |
|---|---|---|
| 新渠道冷启动 | 草稿/能力存在，但无可售组合与有效订单 | 怎样建立可售、可买、可履约、可复盘的最小闭环 |
| 存量经营失速 | 历史客户/订单存在，近期曝光或成交骤降 | 哪个来源、商品、内容或组织环节失去供给 |
| 私域机制停摆 | 分享、店主、体验码、分佣存在但活跃和成交弱 | 机制在哪个关系和行为节点断裂 |
| 商品结构失衡 | SKU 多但英雄品、体验品、复购品不清 | 哪些商品承担获客、成交、利润和复购 |
| 多实体经营 | 同品牌多渠道/多店 | 哪些能力可复用，哪些事实必须按实体重建 |

分类是工作假设；证据变化时允许变更 revision，禁止用一个模板强行解释全部店铺。

## 3. 证据面与质量门

### 3.1 五个证据面

1. **后台观察**：配置、状态、运营入口和当前可见事实；
2. **消费者端观察**：发现、理解、决策、成交、分享和关系旅程；
3. **受治理数据**：AOS Dataset、Profile、Ontology Object/Link 和 Metric；
4. **负责人说明**：线下流程、供货、成本、组织和历史原因；
5. **外部环境**：平台规则、竞品做法、客户需求与合规约束。

数据库/SSH 源发现只能由 Data OS/FDE 通过已批准 DataNeed 执行。Workshop 不直连源库，不接收 SQL、凭据或原始 PII。

### 3.2 证据质量矩阵

每项事实至少记录 `source/scope/window/cutoff/grain/quality/confidence/nonClaims`。常见陷阱：

- 页面空白可能是加载、权限或筛选，不直接解释为业务 0；
- 累计数不代表当前活跃，状态存在不代表产生效果；
- 商品、店主、客户、体验名额、订单和佣金必须有明确分母；
- SQL dump 是 cutoff 快照；即使业务长期停摆、与当前高度相似，也不能称实时库；
- 负责人说明解释规则和过程，不替代规模与一致性证据；
- 单个个人账户不代表全平台总体分布。

结论尽量由两个独立证据面支持。发生冲突时保留两边并进入 reconcile，不选“看起来更合理”的一边覆盖。

## 4. 语义建模

先建关系再算指标。栖月汇至少区分：

```text
商品/SPU → SKU/规格 → 库存/价格/成本
客户 → 订单 → 订单项 → 支付/履约/售后
消费者 → 店主资格 → 个人店铺 → 客户归属
主商品订单 → 体验权益 → 体验码 → 体验订单 → 核销
分享者 → 内容/商品/优惠券 → 访问者 → 绑定 → 首单/复购
推广订单 → 佣金 → 结算/逆转 → 净收益
```

对每条链确定：

- grain、identity、site/weapp/tenant scope；
- 业务状态与终态；
- 事件时间、处理时间、cutoff/watermark；
- 币种、数量单位、退款与逆转；
- cohort 和归因规则；
- PII、许可、保留期和脱敏方式。

无法确认的映射保持 `CANDIDATE/UNKNOWN`，不得为了完成报告强行拼接。

## 5. 三个串行波次

### Wave 1：经营画像

回答“这门生意当前究竟是什么”：

- 建立九维全店扫描；
- 画出商品、客户、店主、订单、体验、分享和佣金关系；
- 区分存量、增量、活跃、沉默和状态库存；
- 标注证据覆盖、数据质量、权限缺口和未知区域；
- 输出 `BusinessDossierRevision`，不提前写增长结论。

完成门：关键指标有分母、时间窗与数据来源；关键关系有身份和状态语义；高影响未知已形成 DataNeed。

### Wave 2：问题与机会

回答“什么阻碍经营、什么值得做”：

- 将现象拆成问题树，不把 GMV 下降直接当根因；
- 每个高影响问题至少保留两个竞争假设；
- 为假设记录支持、反证、可证伪观察和置信度；
- 区分“能力不存在、未配置、未使用、使用无效”；
- 评估机会规模、可达性、时间、单位经济、组织承载和不可逆风险；
- 输出 `ProblemOpportunityRevision`。

完成门：没有单因归因；机会不是功能清单；证据不足的项没有被升级成结论。

### Wave 3：方案设计

回答“采用什么变化机制”：

- 每个方案写出 `输入 → 动作 → 中间信号 → 经营结果`；
- 至少比较维持现状、小规模试验和规模化三个选项；
- 冻结目标 cohort、商品、内容、渠道、预算、owner 和权限；
- 设计先行指标、结果指标、护栏、观察窗和停止门；
- 映射八工作台和 Data/AIP 依赖；
- 输出 `SolutionPortfolioRevision`，仍是 Draft。

完成门：方案可被证伪、可小步执行、可回滚；任何触达、上架、发券、改价、退款或结算仍需独立批准。

## 6. 竞争假设与机会评估

问题卡使用：

```text
现象：什么变化，作用于谁，发生在哪个时间窗
影响：收入/利润/客户/履约/组织
假设 A / B：各自的因果链
支持 / 反证：EvidenceRef
证伪方式：下一条最小证据
置信度：HIGH / MEDIUM / LOW
决策含义：证实后改变什么
```

机会评分不要只看“可能收入”，至少包含：

- 可达客户与真实需求；
- 商品/服务供给和边际成本；
- 毛利、佣金、物流、售后和现金周期；
- 所需内容、销售和客服组织；
- 平台/合规依赖；
- 可逆性与最坏损失；
- 证据成本与学习价值。

## 7. 方案工程化

把好想法变成可运行波次，而不是停留在建议：

1. `Baseline`：冻结现状、scope 与指标；
2. `Readiness`：数据、商品、内容、人员、权限、预算和履约门；
3. `Pilot`：最小 cohort/商品/推广者，明确不做什么；
4. `Observe`：按触点—行为—交易—履约—效果同链记录；
5. `Review`：证据、反证、异常、成本和客户反馈；
6. `Decision`：扩展、修改、停止或回到补证；
7. `Institutionalize`：验证后才固化 SOP、定时任务和规模化预算。

方案不能用发送量、店主数、体验码数、素材数或高佣金比例替代真实增量成交和贡献利润。

## 8. 数据需求与跨层边界

经营探究发现缺口时生成 `DataRequirement`：

```text
businessQuestion / decision
entity / TenantScope / window
requiredGrain / identities / measures
minimumFields / PII class
freshness / quality threshold
expected Dataset/Object/Link/Metric
nonClaims / stop condition
```

流转必须是：

```text
Workshop 缺口
  → DataNeed/Handoff
  → Data OS/FDE 源发现与数据产品
  → Ontology identity/reconcile
  → AIP 画像/假设/方案
  → Workshop 决策与受控执行
```

浏览器全域观察和数据库全域内省是高水平自省的两个入口，但必须以不同身份运行，最终在数据产品与证据层汇合。

## 9. 人工协助契约

需要人工参与不是分析失败。登录、验证码、权限、平台导出、线下规则和真实成本本来就不应由 Agent 猜测或绕过。遇到阻断时生成 `HumanAssistRequest`：

```text
reason / currentStep / blocker
requestedPersonRole
exactAction / targetEntity
readOnlyOrMutation
expectedArtifact / acceptableFormat
cutoff / sensitivity / retention
resumeCondition / timeout / nonClaims
```

### 9.1 可请求事项

- 用户在浏览器中完成登录、扫码、验证码，并确认当前目标店铺；
- 管理员开通只读权限或导出平台报表；
- Data FDE 重新导出 `niushop_b2c_v5.sql` 或获取新的受治理源快照；
- 负责人确认供货、成本、物流、退换、佣金、许可和线下经营事实；
- 人工对冲突对象、关系或指标口径做裁决；
- 对发布、触达、发券、退款、结算等外部动作单独审批。

### 9.2 新 SQL dump 的接收规则

新 dump 至少记录：source/entity、exportedAt 或业务 cutoff、导出方式、文件 SHA-256、Schema/row coverage、敏感级别和提供者。随后：

1. 将其视为新的不可变 Evidence revision，不覆盖旧 dump；
2. 先做 Schema drift、表/字段、粒度、状态和 PII 复核；
3. 与 live Source/Dataset 的水位分开，不因商城低活跃就称其为实时数据库；
4. 由 Data OS/FDE 生成 Profile、Mapping/Dataset/Ontology Candidate 和 Receipt；
5. Workshop 只消费受治理结果，不持有 dump、SQL、SSH 或原始明细。

如果经营长期停摆，可将 dump 标记为“高覆盖历史基线”，并写明为什么接近现状、仍可能遗漏哪些增量。

### 9.3 暂停与恢复

等待人工时将 Analysis Case 标为 `WAITING_HUMAN`，保留第 x/y 步、Checkpoint、已完成证据和精确恢复条件。不得无限等待页面加载，不得用合成值填空，也不得因为人工暂未响应跳过质量门。

## 10. 分析过程与 Checkpoint

经营探究是长程任务。每一步追加 `AnalysisJournalEntry`，不得只保留最终报告：

```text
stepId / wave / question
startedAt / completedAt / actor
actionTaken / evidenceRefs
finding / conflicts / unknowns
hypothesesChanged
status: COMPLETE | WAITING_DATA | WAITING_HUMAN | BLOCKED | SUPERSEDED
nextStep / resumeCondition
```

每个波次完成、发生阻断或人工离开前写 Checkpoint：固定 Case revision、当前第 x/y 步、已完成证据、待履行 DataNeed/HumanAssist、预算消耗和下一安全动作。新证据不得重写旧结论；追加新 revision，并用 `supersedes` 说明变化原因。

分析日志只保存决策摘要和可审计过程，不保存隐含推理链、浏览器凭据、SQL、原始 PII 或完整客户明细。

## 11. 复用节奏

- **首次接入**：全域地图 + 全店基线，不预设单一问题；
- **每日**：订单履约、客户异常、库存、体验权益与外部动作；
- **每周**：来源漏斗、商品角色、客户/店主 cohort、内容和单位经济；
- **每月**：问题树、方案效果、组织能力与资源重配；
- **专题**：体验增长、达人销售、商品结构或复购，但必须继承最近一次全店基线。

已有稳定地图后进入增量模式；只有页面/Schema 漂移、数据质量异常、新机制或证据冲突时重新扩域。

## 12. 输出模板

最终交付至少包含：

1. Executive judgment；
2. Analysis Contract 与证据质量矩阵；
3. 经营画像和对象关系；
4. 问题树、竞争假设与反证；
5. 机会地图与优先级；
6. 方案组合、理论变化链和波次；
7. 指标、护栏、停止门和审批点；
8. DataRequirement 与八工作台承接；
9. 冲突、未知和 nonClaims；
10. HumanAssistRequest 与恢复条件；
11. AnalysisJournal、Checkpoint 与 revision 变化；
12. 下一次复跑条件。

文字统一使用“决策摘要、证据链、归因路径、关键假设和不确定性”，不保存或声称模型隐含推理链。
