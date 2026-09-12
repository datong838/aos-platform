# 栖月汇真实经营闭环：当前进度与下一阶段

2026-09-12 14:05，基线9e341bef。目标仍是可安装、配置、禁入、恢复、卸载重装，并由真实数据自然完成经营闭环。不能给出有依据的总完成百分比：工程清册、运行实证和经营效果是不同分母。

## 大阶段

| 阶段 | 当前证据 | 尚缺 |
|---|---|---|
| 领域包与生命周期 | 本地真实安装、配置、enable；实际低电量休眠过期后禁入、清理、disable、uninstall及新代重装 | 持续观察，业务执行中不同等待节点的恢复尚未验证 |
| 当前真实接入与工作台入口 | 当前源连接器存在；新代3容器健康；目录如实提示没有可见入口 | 原SSH认证拒绝未恢复；源/管道未登记；调度登记权限范围待答复 |
| 自然经营首链 | 九项宿主操作、Case/Run、分析、评审、内容能力和Receipt有代码 | 当前源事件、计划绑定、occurrence、dispatch绑定均0；事件消费生产入口未发现，未发生真实首链 |
| 八工作台经营场景 | 已有业务任务图谱和工作台实现 | 每条实际来源→方案→任务→产物→复盘证据、连续窗口和恢复验证 |
| 发布决定 | 尚未进入 | 首链/八场景/连续观察完成后再评审；不push，230 L0挂起 |

## 本次核对的关键区别

1. growth包的handle仍以登记和部分纯校验为主，但不能据此说九项经营操作未实现：ecommerce_growth_host_composition.py已装配九个HostService，其实现位于ecommerce_growth_runtime_adapters.py，canonical router执行前验证dispatch。
2. automation_occurrence_store.py有事件与周期Occurrence持久化；automation_dispatcher.py有单次claim/Receipt；aip_logic_automation_scheduler.py有weekly槽位枚举。对生产Python调用点搜索仅找到定义，没有找到run_due_schedule_binding和dispatch_one_occurrence的生产调用者；record_event也没有找到接入数据源的调用点。该结论是代码接线缺口，不代表测试不存在。
3. ecom_consistency_store.py在权威提交中写projection_outbox；ecom_projector.py已有投影消费者。经营消费必须独立确认，不得占用或改写投影器projected标记。
4. 06:04:55Z同租户只读查询：projection_outbox无行、automation_schedule_binding=0、automation_occurrence=0、extension_operation_dispatch_binding=0。详见natural-chain-current-counts.json。未输出业务正文或凭据。
5. GrowthPlanGenerationService只接受已有受治理running D03 AgentRun与当前DecisionSummary，不负责空计划起跑。不能为了生成一份计划绕过画像、证据或来源门。

## 下一阶段实施顺序

1. 权威源事件读取合同：复用projection_outbox，只接收authoritative_store；验证tenant/project/workspace、事件键、载荷hash和事务引用，独立消费游标，禁止把legacy_post_projection当真实触发。先提供只读验证器和隔离测试，不消费主库历史或触发业务。
2. 事件接续Owner：读取已配置、已获准的Case类型与方法版本，生成稳定事件身份；同事务记录Occurrence与独立消费Receipt。启动、重复事件、双写者、崩溃后重放必须有实际PG验证；未知执行结果仅reconcile。涉及新增表或角色访问时独立评审，不套用待答复的路由登记范围。
3. 空计划路径：复用initial_store_analysis而非发明第二种Case对象；当前可靠画像缺失先画像，数据缺失进入原Run WAITING_DATA，补齐后恢复；已有画像再排序最多三个候选。不能预填假计划或跳过D1-D5。
4. 持续执行入口：将已存在的due计算和dispatch接入受监管单写者生命周期；按当前安装generation/epoch和配置重校验，禁用即拒绝新Admission。配置安装时完成，不能每次业务让开发者组装参数。
5. 首链固定验收：真实商品/SKU修订→商品尖刀验证→来源化候选→exact方案评审→运营准备、内容教育任务、媒体产物、价格经济性复核→产物人工评审后自动续跑→总控复盘→Wiki候选。每一跳保留同一Case/Run和前驱Receipt。

## 八场景与效果证据

| 顺序 | 真实业务问题 | 核验产物/结果 |
|---|---|---|
| 1 | 哪1–3个真实商品值得优先教育验证 | 商品候选依据、可读文案/图片或短视频、内部准备完成Receipt |
| 2 | 今日订单履约/售后异常如何处置 | 分诊任务、原因、恢复及可核验处理结果 |
| 3 | 体验领取到使用/复购哪里流失 | 同意、体验Offer、逐对象执行凭据及领取/履约回读；外发对象和内容需明确授权 |
| 4 | 哪种内容教育带来自然转化 | 内容版本、渠道约束、质量评审、归因和效果窗口 |
| 5 | 当前成本/佣金下什么方案有收益 | 单位经济性、预算、价格影响预览与实验止损 |
| 6 | 内部店主或创作者谁能稳定交付 | 资格、任务、交付质量、归因证据 |
| 7 | 微信小店一个商品如何走到首单 | 渠道配置、商品/履约准备、已授权发布和首单证据 |
| 8 | 周/月经营方法该保留还是修订 | 跨场景复盘、反例、方法置信度与待审Wiki候选 |

沿用产品方案每场景至少三个计划窗口和一次受控恢复。窗口未到或样本不足明确待观察，不能用模拟时间或fixture替代商业效果。上述任务目前是验收计划，不是执行完成记录。
