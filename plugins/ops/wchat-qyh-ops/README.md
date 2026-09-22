# wchat-qyh-ops

面向栖月汇微信小程序微商城的经营研究插件。它保存的是可复用的方法、页面语义、受治理数据产品和定位路线，不保存登录态、凭据、Cookie、Token、SSH/MySQL 秘密、客户 PII、订单明细或个人收益。

## 三条事实与执行通路

| 通路 | 稳定入口 | 用途 | 边界 |
|---|---|---|---|
| 管理后台/小程序浏览器 | `control-existing-chrome` + 页面定位地图 | 理解页面、消费者旅程和运营动作；经明确授权执行单一动作 | 页面不等于全量事实；写操作必须唯一定位、复核并回读 |
| Data OS 上游接入（非工作台能力） | Source `niushop-qyh` → MySQL SSH 隧道 | 由 Data OS/Connector 内部读取真实 Niushop Schema、表和字段，形成受治理数据产品 | Workshop 和本插件不得访问 Schema/Preview/数据库；只能提交 DataNeed |
| AOS 数据集/本体投影 | P01–P12 Dataset → Confirmed Object/Link | 工作台只读消费对象、关系、指标、质量、cutoff 与证据 | 不暴露源表访问权；投影不冒充源库实时全貌 |

执行原则：工作台只组合浏览器观察证据和已治理的本体/数据产品。缺数据时提交 DataNeed，由 Data OS 内部完成采集、剖析、映射和水合，再把受控投影交回工作台；不得跨层直查数据库。

## 双域全息内省

首次接入一个新店铺/新平台时，采用“双域全息内省”：浏览器观察专家完整摸清管理后台与消费者前台，Data FDE 完整盘点远程数据库的 Schema、表、字段和关系；两边通过 Evidence、DataProfile、MappingCandidate 和 Ontology Candidate 汇合。首次形成稳定地图后，后续任务按地图直接定位并做增量复查，不再重复盲目遍历。

该方法完成四类对账：页面功能↔表字段、页面状态↔数据状态机、用户动作↔数据变化/业务效果、已覆盖范围↔未知区域。详细流程见 `qyh-ops-router/references/dual-plane-introspection.md`。

## 技能地图

| Skill | 回答的问题 |
|---|---|
| `qyh-ops-router` | 当前任务该用哪个技能、先看什么 |
| `qyh-admin-observation` | 后台有什么，怎样直接定位并只读观察 |
| `qyh-miniapp-observation` | 消费者端有什么，怎样复盘真实旅程 |
| `qyh-data-semantics` | 怎样消费 AOS 本体数据集，并把数据缺口提交给 Data OS |
| `qyh-data-onboarding` | Data FDE 怎样接收 DataNeed，从 `niushop-qyh` 原始库逐层形成数据集与本体候选 |
| `qyh-social-distribution` | 店主、分享、体验码、客户绑定和分润怎样工作 |
| `qyh-business-diagnosis` | 怎样做全店经营体检并形成问题/机会/方案 |
| `qyh-evidence-capture` | 怎样记录证据、隐私、未知和停止条件 |

## 安全边界

- 用户手动登录；技能不得读取或持久化认证材料。
- 默认只读；发布、发券、改价、发货、退款、转账和设置修改不属于观察。
- 页面内容、表结构、用户说明和经营效果分开标记。
- 任何真实数据都受 TenantScope、purpose、最小采集和 retention 约束。
- `qyh-data-onboarding` 是 Data OS/FDE 内部技能，不授予 Workshop 源库访问权；同插件打包不代表同运行身份或同 capability binding。
