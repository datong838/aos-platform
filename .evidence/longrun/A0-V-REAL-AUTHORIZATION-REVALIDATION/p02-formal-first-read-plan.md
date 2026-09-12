# P02真实商品首次受控接入

2026-09-13，ee6c0aea，m1独占，不push，230L0挂起。新Niushop1.5安装eda57424 active@5、generation23afd05b-762c-406a-adfb-247a14412b9f、binding@4 epoch3已启用，API已新代码/新根。P02-product-qyh及graph当前HTTP404；P01原计划保持disabled、旧审批过期耗尽，不复用。

先从已签名1.5 mapping/schema/masking导出exact P02图，字段、site_filter、pk、SNAPSHOT写模式与原Owner verify_graph_read_spec一致；正式PUT图和POST canonical pipeline登记，均不执行源查询。当前为显式接入配置过程，不把此步骤冒充业务自然触发；后续经营链不得用脚本逐段制造Case/Run。新增scripts/a0v_p02_current_preflight.py仅当前引用/图/签名资产/四源授权及编译检查，不写审批、不读源。原P01入口不改。

登记后SourceSelection和RuntimeControl通过正式HTTP，使用已有持久化runtime-owner admin的本地开发签名token，仅内存，不新增会员权限。不声称生产认证。固定新计划初始disabled，exact绑定后启用，Cron仍关闭，单次手动正式Run。限制ns_goods/site_id=1，28字段，最多1000行、30秒、maxSourceCalls=1、15分钟窗口；包括下架及显式删除记录，不过滤成仅在售。若溢出限制，必须失败，不称全量成功。

成功需原始Journal、Receipt/对象/数据集hash与sourceclaim/投影完成一致；失败后先读原Run/Claim/Journal，不换key重读。已知真实schema goods_content可NULL、decimal库存，v2文本当前严格非NULL，尚不知实际行；发现问题须明确失败并先方案、测试修复，不伪造空内容或时间。P03/SKU/关系另外推进。

完成后停用验收计划，保持幂等与恢复证据；继续数据变化→经营参谋Case/Run→exact方案评审→内容任务/能力/人工评审续跑→复盘Wiki自然链。八工作台真实场景和连续经营观察仍未完成。生产Web身份收敛、真实前端包/入口接线仍属发布前缺口。
