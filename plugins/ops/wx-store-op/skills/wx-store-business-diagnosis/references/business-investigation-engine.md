# 微信小店经营探究引擎

## 目录

1. 分离渠道与经营实体
2. 探究合同
3. 店铺生命周期分类
4. 证据与语义质量
5. 三个串行波次
6. 微信小店专项分析
7. 竞争假设与方案工程化
8. DataRequirement 与工作台承接
9. 人工协助契约
10. 分析过程与 Checkpoint
11. 复跑节奏
12. 输出模板

## 1. 分离渠道与经营实体

微信小店是渠道；“栖月汇、裕威参行”等是该渠道下的经营实体。顶部渠道选择器回答“看哪个平台”，实体选择器回答“分析哪家店”。每个实体独立持有：

- 店铺身份、主体、开店时长和权限；
- 商品、订单、客户、内容与体验；
- 关联账号、联盟、会员、券和营销配置；
- 数据覆盖、经营基线和 Analysis Case。

跨店比较只能使用对齐后的指标口径、时间窗和生命周期阶段，不把新店与成熟店直接按 GMV 排名。

## 2. 探究合同

每个 Analysis Case 冻结：

```text
channel / entity / caseId / revision
analysisType / businessQuestion
scope / metricWindow / collectedAt
allowedEvidence / permissionBoundary
baselineRef / decisionOwner
nonClaims / stopCondition
```

`analysisType` 至少支持：首次全店基线、每周复盘、体验增长专题、达人销售专题、商品结构专题和历史关闭记录。它们是同一经营探究工作区的不同 Case，不是新的一级菜单。

## 3. 店铺生命周期分类

| 形态 | 判断重点 | 典型首要动作 |
|---|---|---|
| 新店冷启动 | 在售、审核、物流、售后、客服、首批有效订单 | 关闭上架门，校准审核，3～5 品最小组合，真实首单闭环 |
| 存量增长失速 | 历史底盘、近期来源漏斗、老客/新客、内容与推广 | 找出衰退起点和可复制来源，不把服务分高误写成增长健康 |
| 商品结构问题 | 流量/成交/利润/复购角色、价格带、问题商品 | 区分英雄、体验、复购、利润和形象商品 |
| 达人/联盟停摆 | 商品、佣金、达人/机构、内容、订单、结算 | 检查是否同链，不把佣金配置当动销 |
| 多店/多渠道 | 可复用资产与实体差异 | 保留实体独立事实，再抽取平台方法 |

### 3.1 新店冷启动专门门

新店必须按以下顺序分析：

1. **可发布**：类目、资质、标题、图片、规格和审核；
2. **可履约**：发货地址、运费、库存、客服、售后和退货；
3. **可盈利**：成本、平台费用、物流、佣金、退款和贡献利润；
4. **可经营**：3～5 个商品角色、首页、内容、首批外部客户；
5. **可学习**：来源—内容—商品—订单—履约—反馈同链。

草稿存在不等于可发布，页面“0”在无在售商品时不是转化诊断。首批有效订单不能依靠刷单、自买自卖、抽奖或异常低价制造。

### 3.2 存量店专门门

分开报告：

- 历史资产：累计成交、老客、评价、服务和商品沉淀；
- 当前增量：近期曝光、点击、下单、成交、退款和来源；
- 经营供给：内容、直播、短视频、搜索、推荐、联盟、会员和复购节奏。

环比骤降可能有基数事件，必须补查上周期来源，不能直接写“自然衰退”。

## 4. 证据与语义质量

### 4.1 证据层

- `PLATFORM_CAPABILITY`：平台提供某功能；
- `OBSERVED_STORE_FACT`：目标实体页面当前可见事实；
- `GOVERNED_DATA`：受治理 Dataset/Object/Metric；
- `OWNER_EXPLANATION`：经营规则和线下过程；
- `BUSINESS_HYPOTHESIS`：待证伪解释；
- `PERMISSION_BLOCKED/UNKNOWN`：权限、加载或口径不足。

每条事实记录 `entity/page/window/collectedAt/grain/quality/nonClaims`。明确无权限即停止该页；加载中、空白或筛选未完成不能写成 0。首页累计、商品列表、数据中心和结算口径发生冲突时保留冲突并请求对账。

### 4.2 四状态模型

任何能力都分四级：

1. 平台提供；
2. 店铺已开通/配置；
3. 被真实使用；
4. 产生可归因效果。

例如会员入口、联盟、优惠券、关联账号或自动推广不能因页面存在就被写为经营能力已运行。

### 4.3 指标语义

至少明确：

- 曝光人数/次数、点击人数/次数；
- 下单/支付/结算/退款的状态与时间窗；
- 新客、老客、会员、访问和复购 cohort；
- 商品、SKU、订单、订单项、达人/机构与佣金粒度；
- 推荐、搜索、直播、短视频、分享、卡包和联盟来源；
- 金额币种、含税/退款、平台费、物流与佣金。

## 5. 三个串行波次

### Wave 1：经营画像

- 冻结店铺生命周期与分析问题；
- 扫描店铺、商品、流量、交易、客户、内容、推广、利润和组织；
- 绘制来源—内容—商品—客户—订单—履约关系；
- 建立证据覆盖、权限、加载、数据质量和未知矩阵；
- 输出 `BusinessDossierRevision`。

完成门：关键数字有实体、分母、时间窗和来源；不把平台规则示例当店铺事实。

### Wave 2：问题与机会

- 将 GMV/订单变化分解到曝光、点击、下单、支付、履约和复购；
- 每个高影响问题保留至少两个竞争假设；
- 区分缺能力、未配置、未使用和使用无效；
- 评估机会的客户可达性、单位经济、组织承载、平台门和风险；
- 输出 `ProblemOpportunityRevision`。

### Wave 3：方案设计

- 比较维持现状、小规模试验和规模化选项；
- 写出 `输入 → 动作 → 中间信号 → 经营结果`；
- 冻结 cohort、商品、内容、达人、预算、owner 和权限；
- 给出先行指标、结果指标、护栏、观察窗和停止门；
- 形成八工作台 Handoff 和 DataRequirement；
- 输出 `SolutionPortfolioRevision`，保持 Draft。

证据不足时允许回退前一波补证，不能静默修改结论。

## 6. 微信小店专项分析

### 6.1 商品发布与经营角色

商品审查不只看是否在售，还要看：类目/资质、标题、短标题、图片、详情、规格、重量、价格、库存、运费、售后、合规和单位经济。商品角色至少区分：

- 审核校准品；
- 体验/获客品；
- 核心成交品；
- 复购品；
- 利润品；
- 高端形象品。

不要把所有草稿一次发布，也不要用低价商品制造“有效经营”假象。

### 6.2 推荐、搜索与内容

- 推荐资格、推荐曝光和推荐成交分开；
- 搜索词、曝光、点击和商品承接分开；
- 直播/短视频/公众号能力、内容产量、内容质量和成交效果分开；
- 平台成长建议只作对照，不直接成为店铺目标。

### 6.3 老客、会员与复购

老客人数高可能是资产，也可能意味着新客枯竭。会员必须区分入口、权益、开卡、活跃和增量效果；券和触达必须携带许可、频控、对照组与利润护栏。

### 6.4 达人、机构与联盟

完整链路是：

```text
推广商品 → 佣金/服务费 → 达人或机构 → 内容 → 曝光/点击
→ 订单/退款 → 佣金结算 → 净增量效果
```

任一节点缺失都不能写“达人销售已建立”。

## 7. 竞争假设与方案工程化

问题卡：

```text
现象 / 影响 / scope / window
假设 A / 假设 B
支持 / 反证 / 可证伪观察
confidence / nextEvidence / decisionImplication
```

方案卡：

```text
targetCohort / businessGoal
theoryOfChange
product/content/channel/owner
cost/unitEconomics/dependencies
leadingMetrics/outcomeMetrics/guardrails
approval/stop/rollback/nonClaims
```

方案执行采用 `Baseline → Readiness → Pilot → Observe → Review → Decision → Institutionalize`。只有小样本结果支持理论变化链后才扩大商品、客户、达人或预算。

## 8. DataRequirement 与工作台承接

经营参谋不得直接登录微信小店、抓页面或调用渠道 API。数据缺口形成：

```text
businessQuestion / decision
channel / entity / TenantScope / window
requiredGrain / dimensions / measures
freshness / quality / PII
expected Dataset/Object/Link/Metric
nonClaims / stopCondition
```

由接入层、Data OS、Ontology 和 AIP 逐层返回受治理事实。工作台只消费 Dataset、Object/Link、Metric、Evidence 与 Receipt。

八工作台承接：

- 经营参谋：画像、问题、机会和 SolutionPortfolio；
- 日常总控：Task、Checkpoint、Review 和 Handoff；
- 内容与活动：内容/活动 Brief 与评审；
- 统一运营：商品订单履约和异常；
- 达人邀约：候选、邀约、合同和交付；
- 多媒体：素材 revision、质量门和许可；
- 价格治理：单位经济、佣金和 ImpactPreview；
- 客户关系：Consent、Segment、Journey 和 Effect。

任何发布、改价、发券、触达、退款或资金操作仍走独立 Proposal/Approval/Lease/Receipt/Reconcile。

## 9. 人工协助契约

浏览器登录、扫码、验证码、店铺切换、账号权限和平台导出属于正式的人机协作步骤，不应被自动化绕过。阻断时生成：

```text
reason / currentStep / blocker
requestedPersonRole
exactAction / targetStore
readOnlyOrMutation
expectedArtifact / cutoff
sensitivity / retention
resumeCondition / timeout / nonClaims
```

可请求：

- 用户完成扫码登录、验证码并确认店铺实体；
- 店铺管理员开通只读统计权限；
- 人工下载商品、订单、售后、达人或结算报表；
- 负责人确认成本、库存、供货、合规、组织过程和平台外渠道；
- 对平台指标冲突、商品映射或客户许可做人工裁决；
- 对任何真实店铺修改单独审批。

人工导出文件必须记录来源页面、店铺实体、筛选条件、指标时间窗、导出时间、SHA-256、敏感级别和提供者。它是带 cutoff 的 Evidence revision，不是持续 Connector；进入工作台前仍需经受治理导入、质量、语义和本体门。

等待人工时将 Case 标为 `WAITING_HUMAN`，保留第 x/y 步、Checkpoint 和恢复条件。明确“暂无权限”立即停止该页；加载不确定只允许有限重试，之后记录 `LOADING_UNCERTAIN`，不得把空白写成 0。

## 10. 分析过程与 Checkpoint

为长程、多页面、多权限任务追加 `AnalysisJournalEntry`：

```text
stepId / wave / question
startedAt / completedAt / actor
pageOrDataAction / evidenceRefs
finding / conflicts / unknowns
hypothesesChanged
status: COMPLETE | WAITING_DATA | WAITING_HUMAN | BLOCKED | SUPERSEDED
nextStep / resumeCondition
```

页面切换、店铺切换、波次完成、权限阻断或人工离开前写 Checkpoint，固定渠道、实体、Case revision、当前第 x/y 步、已完成证据和下一安全动作。恢复时先读 Checkpoint，使用导航地图直达未完成页面，不重新全量摸索。

新数据使用新 revision，通过 `supersedes` 说明为什么修改画像、假设或方案；不得静默覆盖旧报告。日志只保存决策摘要和证据路径，不保存凭据、原始 PII 或模型隐含推理链。

## 11. 复跑节奏

- 首次全店分析：建立基线和优先问题；
- 每周复盘：来源漏斗、商品角色、内容、客户和履约；
- 专题分析：体验增长、达人销售、商品结构；
- 历史关闭：保留 revision、cutoff、决策和关闭原因；
- 多店比较：生命周期对齐后再比较，保留实体差异。

平台或店铺地图稳定后进入增量观察，不每次重摸全部菜单；出现页面变化、权限变化、口径冲突或新问题才扩展观察。

## 12. 输出模板

1. Executive judgment；
2. Analysis Contract；
3. 证据质量与权限矩阵；
4. 经营画像和关系图；
5. 问题树、竞争假设和反证；
6. 机会地图与优先级；
7. 方案组合、波次和单位经济；
8. 指标、护栏、停止门和审批点；
9. DataRequirement 与工作台 Handoff；
10. HumanAssistRequest 与恢复条件；
11. AnalysisJournal、Checkpoint 与 revision 变化；
12. 冲突、未知、nonClaims 与复跑条件。

使用“决策摘要、证据链、归因路径、关键假设和不确定性”，不保存或声称模型隐含推理链。
