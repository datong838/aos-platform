# AR2 N1～N8 源码闭包施工清册

基线：`aos-platform/m1@648754a1`；authority：`AOS-000559`；生成日：2026-09-07。本文只冻结当前源码去向与施工顺序，不代表迁移、安装或业务运行已经完成。

## 1. 当前结论

- 231-1 指定的 25 个种子文件全部存在，共 14,789 行；本清册还覆盖其直接领域依赖与反向调用方，不能用 25 个种子数量代替传递闭包。
- `bundles/domains/ecommerce-core`、`bundles/solutions/ecommerce-growth`、`bundles/platforms/ecommerce-niushop` 当前只有声明与内容资产，没有 `backend/` 可执行包。
- `services/aos-api/aos_api/main.py` 仍静态启动 `aip_logic_automation_scheduler`；`routers/ecommerce_business_investigations.py` 与 `routers/ecommerce_workshop.py` 仍直接导入电商业务实现。
- 因此 AR2 不能只改 bundle.yaml；必须同时交付包内后端、通用 occurrence/预算 ports、受控注册入口和旧 Router 单写转发桥。

## 2. 逐文件去向

`preHash` 均为 SHA-256；`保留公共` 表示代码留在平台但只通过 SDK port 暴露，`迁入` 表示包内取得业务实现权，旧文件在切换期只保留兼容转发。

| N | sourcePath | targetPath | layer | decision | reason | preHash |
|---|---|---|---|---|---|---|
| N1 | `services/aos-api/aos_api/ecommerce_business_investigation_case.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_case.py` | solution | 迁入 | Case 是经营增长业务权威 | `cf19aae24f37ff56393bb1b2d4631c4c5d126cb849b2b1cef7f002eb2dacf1e8` |
| N1 | `services/aos-api/aos_api/ecommerce_business_investigation_schedule.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_schedule.py` | solution | 迁入 | SchedulePolicy 属于经营分析业务 | `507dc1fb42d545953598c52fa34b9e45bd42267ec79a4f805dbfc6887741f13e` |
| N1 | `services/aos-api/aos_api/ecommerce_business_investigation_application.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_application.py` | solution | 迁入 | Case/Run 应用协调属于 growth | `86c27b6806b61e19f6dc197bcb625e58d42b792b383efa40f59603a093f07206` |
| N2 | `services/aos-api/aos_api/aip_logic_automation_scheduler.py` | 原路径 | platform | 保留公共并改造 | 通用调度进程不能进入电商包 | `66a0ec6a324c1a80589d7256cf961053ae1e6dd9ec1e1fc10a005cc051358668` |
| N2 | `services/aos-api/aos_api/aip_logic_automation_store.py` | 原路径 | platform | 保留公共并改造 | 通用政策与运行权威由平台持有 | `321d4f242375ff05f20f2fdb40c9fd706f3bd8851f347959df1533ec56eea3c5` |
| N3 | `services/aos-api/aos_api/business_investigation_niushop_profile.py` | `bundles/platforms/ecommerce-niushop/backend/ecommerce_niushop/business_investigation_niushop_profile.py` | adapter | 迁入 | 含 Niushop 特有发现与映射 | `b2e2c787afe694b61d1b377ba80097861e3ff790600821ee7abad3dedb02e247` |
| N3 | `services/aos-api/aos_api/business_investigation_mapping.py` | 原路径 | data | 保留公共并端口化 | 通用来源字段到本体映射权威 | `f897c5edbb8f51045efeac1ce86c0894e62ff3647065155d4c9b7e4de38ee3e5` |
| N3 | `services/aos-api/aos_api/business_investigation_hydration.py` | 原路径 | data | 保留公共并端口化 | 通用语义水合与 owner receipt 权威 | `6e07667f793db79dc6b0ea9fec0530df5d856bd1a29c0ddeaf3ab4989bf343f9` |
| N3 | `services/aos-api/aos_api/data_requirement_store.py` | 原路径 | data | 保留公共并端口化 | DataRequirement 是公共数据权威 | `441e91a05b049918d92f1011ff3e545493c1159d21be0aca52d906e5b97e6763` |
| N3 | `services/aos-api/aos_api/data_requirement_outbox_store.py` | 原路径 | data | 保留公共并端口化 | Fulfillment outbox 是公共可靠投递 | `f30c47b97f7c2e46ade99b26fd77ec4fe5a44aa1e8aa423699cd7f43c8044cf6` |
| N4 | `services/aos-api/aos_api/aip_business_investigation_compiler.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/aip_business_investigation_compiler.py` | solution | 迁入 | BI 专用编译规则不属于 AIP 内核 | `c6a4cb92aac45db736325b1c6f69666873a8c7f7a6add09b79dcb2c16a9b482c` |
| N4 | `services/aos-api/aos_api/aip_business_investigation_compile_saga.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/aip_business_investigation_compile_saga.py` | solution | 迁入 | BI 专用编译 Saga | `9afeb4fecbca0dc66faff9a38500b9546bc9828e2069f034018c35eb740c0e7a` |
| N4 | `services/aos-api/aos_api/aip_business_investigation_runtime.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/aip_business_investigation_runtime.py` | solution | 迁入 | 反向依赖电商 Run，必须移出内核 | `9cc088d96a295c84c1751f2daf9f702cee9a0f3557d093ce78cfd905dc4f1d05` |
| N4 | `services/aos-api/aos_api/aip_business_investigation_data_saga.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/aip_business_investigation_data_saga.py` | solution | 迁入 | BI 数据协调属于 growth | `d7e0009b16a1e24a503b9a3c3ce8883958b18592bb9c16136d4b155a8d5660ea` |
| N5 | `services/aos-api/aos_api/ecommerce_business_investigation_review_command.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_review_command.py` | solution | 迁入 | 三阶段评审推进是领域规则 | `67e47bbbfd160d051406ee72b56084271b5b92790dbd732d6b3d3cb4eb5504f2` |
| N5 | `services/aos-api/aos_api/ecommerce_business_investigation_handoff.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_handoff.py` | solution | 迁入 | 建议到内容任务的领域交接 | `be06a4915659af1ec8fe9527c255e7253ab734772bd9279b8bf7def3b466b3d3` |
| N6 | `services/aos-api/aos_api/ecommerce_content_campaign_workflow.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_content_campaign_workflow.py` | solution | 迁入 | 内容承接业务流程属于 growth | `fad7222eb332284767b07f4ec2254426cb1b2f504d6413f91feaafb044ac6e70` |
| N6 | `services/aos-api/aos_api/ecommerce_content_campaign_workflow_contracts.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_content_campaign_workflow_contracts.py` | solution | 迁入 | 与领域流程共同版本化 | `9bf01391c6acb019e48398220d94ab36708463761146b763fc3131e1ed987529` |
| N7 | `services/aos-api/aos_api/aip_agent_run_executor.py` | 原路径 | aip | 保留公共并加预算门 | 所有领域共用真实能力执行 | `c16c921e40131c62f7fe01d14a8a6513fb8f1677f568cc7380812c22bbdc4ed9` |
| N7 | `services/aos-api/aos_api/aip_model_runtime_resolver.py` | 原路径 | aip | 保留公共 | exact 模型路由是通用权威 | `7b75a8a0370d4eef543fa2a4fe676952104c66e82b970e7b468b21040f0f8121` |
| N7 | `services/aos-api/aos_api/aip_llm_adapter.py` | 原路径 | aip | 保留公共 | Provider 调用适配为通用能力 | `94ad9245b3a84143da2a74dacd6fb35055c8b565a6be3a59fb6c20c51af28d1c` |
| N7 | `services/aos-api/aos_api/aip_provider_usage_bridge.py` | 原路径 | aip | 保留公共并加结算 | UsageReceipt 不能由领域包自写 | `2ec258b2edb7dc164cfeafb56a1f06c7e6cd47389a7544393c314669460ee4ba` |
| N8 | `services/aos-api/aos_api/aip_production_contract_store.py` | 原路径 | aip | 保留公共并端口化 | 公共生产合同权威 | `4293e19c7faa0f514a44228f0751c9ea7c33f4d4d703017a24f85969b5c041f3` |
| N8 | `services/aos-api/aos_api/aip_effect_review_store.py` | 原路径 | aip | 保留公共并端口化 | EffectReview 是跨领域公共权威 | `c8223e2460c5d529fe9871415eaadd03e8d06cb48c3e8b97d4496197d6458e41` |
| N8 | `services/aos-api/aos_api/ecommerce_workshop_task_cockpit.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_workshop_task_cockpit.py` | solution | 迁入 | 总控业务投影属于电商增长方案 | `f85986ef159ee5fa3639776c48ed7eae0ef71a0b3f7fe6823d59b24542261e57` |

## 3. 依赖闭包决策

直接依赖分三类处理：

1. `aip_*`、`db`、`tenant_scope`、`auth`、`public_contracts` 等公共权威不复制，通过 `sdk_ports.py` 的 operationId 与 exact refs 调用。
2. `ecommerce_*`、BI 专用 application/compiler/review/handoff/cockpit 迁入 growth；迁移期旧模块只做安装绑定后的兼容转发，不保留第二写者。
3. Niushop profile 与 connector 进入 Adapter；通用 mapping/hydration/DataRequirement 留在 Data 层，Adapter 只产出受控 Observation/Fulfillment。

种子与新增迁移节点按固定点继续展开后，以下 19 个业务依赖也必须纳入迁移，不能继续由包直接导入平台私有模块：

| source module | target | decision | preHash |
|---|---|---|---|
| `services/aos-api/aos_api/business_investigation_shared_contracts.py` | `bundles/domains/ecommerce-core/backend/ecommerce_core/contracts.py`＋`packages/aos-extension-sdk/python/aos_extension_sdk/contracts.py` | 电商事实合同进 core；通用 ExactRef/信封进 SDK；旧模块仅兼容转发 SDK 类型，平台绝不 import bundle | `3efeb79094e2ad41e273fca64ced9c3464f9cd4c7f7409940dadbb19be372843` |
| `services/aos-api/aos_api/aip_business_investigation_data_requester.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/aip_business_investigation_data_requester.py` | BI 专用数据请求桥迁入 growth | `9cdc9a27c44f7e9126b2181d2cc09b4f714e5a44041589c8fd3df9b11db55746` |
| `services/aos-api/aos_api/ecommerce_analyst_authority_contracts.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_authority_contracts.py` | 迁入 growth | `694e86a477197ffb79cb45d8fa2fb13fc092680d12c2d83479c934a6b0b15e94` |
| `services/aos-api/aos_api/ecommerce_analyst_authority_store.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_authority_store.py` | 迁入 growth，存储改走 SDK | `c6c6b0847646aa7435cfe39c46ce07bfb35c619b74b49bf1d46d4b63196af4d9` |
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_approval.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_approval.py` | 迁入 growth | `9d3013da2cfb7f78bc5075183a986155a5515a3ecb24e02abed35ec42b834728` |
| `services/aos-api/aos_api/ecommerce_business_investigation_case_selection.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_case_selection.py` | 迁入 growth | `2d3b41a04b7e66efb3ee19dc95441264de373659b03cb66dc29c6b5ff4dac52c` |
| `services/aos-api/aos_api/ecommerce_business_investigation_data_command.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_data_command.py` | 迁入 growth | `9b5737f79f1e062ccb4fd6817faf20fd0cbb16fbe1531cf2e6086154192d53f6` |
| `services/aos-api/aos_api/ecommerce_business_investigation_projection.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_projection.py` | 迁入 growth | `f1d4846f898c4caf49e447c82cae1a9916f5ca71448f91db1db3b7b95b50332d` |
| `services/aos-api/aos_api/ecommerce_business_investigation_run.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_run.py` | 迁入 growth | `7c2db302485eecb926c3fad41f225845c668048b49b915669d5cbb46cd91bcf2` |
| `services/aos-api/aos_api/ecommerce_workshop_catalog.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_workshop_catalog.py` | 迁入 growth | `c7baa6b6b484c95125cae59496200363aa120d6ac65b40d09c56a8c961b501d2` |
| `services/aos-api/aos_api/ecommerce_workshop_content_campaign.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_workshop_content_campaign.py` | 迁入 growth | `7779517ed8617d2b0e4939e5f7db698087f8f3a808c9f80bf6aa933cd486c79d` |
| `services/aos-api/aos_api/ecommerce_workshop_handoff_contracts.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_workshop_handoff_contracts.py` | 迁入 growth | `ad3da43c641f8805c4e2661cb071d97e8ec6822bf27be0298c5b732f5a2cee0e` |
| `services/aos-api/aos_api/ecommerce_workshop_handoff_service.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_workshop_handoff_service.py` | 迁入 growth，任务命令改走 SDK | `07bcc6ae309c876cf9e502ea15a7bbbea390902ed37d7cdd9e9d99feb424f0f5` |
| `services/aos-api/aos_api/ecommerce_workshop_task_cockpit_contracts.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_workshop_task_cockpit_contracts.py` | 迁入 growth | `1b703e0e0f9210cbea2e5c6732f9ef4d966c3a15e16bd132d8fc0e2457f3b3b8` |
| `services/aos-api/aos_api/ecommerce_workshop_contracts.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_workshop_contracts.py` | 迁入 growth；旧路径仅作序列化 DTO 兼容转发 | `a03218f42b50e1807b9165c7bf0b28179144554e3d284ec0441fb7135088f044` |
| `services/aos-api/aos_api/ecommerce_workshop_content_campaign_contracts.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_workshop_content_campaign_contracts.py` | 迁入 growth | `84b40e90191c4033709528a0ba9acbf437f310bbc77e2c5330f0f0cdfcb50598` |
| `services/aos-api/aos_api/ecommerce_content_campaign_authority_store.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_content_campaign_authority_store.py` | 迁入 growth；存储操作改走 SDK storage port | `67362f4692cd1738f89dade9d9d8989893bb112f35a9a913df92f1acdedfe07d` |
| `services/aos-api/aos_api/ecommerce_content_campaign_authority_contracts.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_content_campaign_authority_contracts.py` | 迁入 growth | `1ba3074c23e6dfc3ec74aeda144ea0b3b5f43dc84c0677ea7a1df01624e4fa9f` |
| `services/aos-api/aos_api/ecommerce_business_investigation_aip_authority.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_aip_authority.py` | 迁入 growth；StageTemplate 查询通过公共 SDK port 注入 | `547f4d96bd5bd65f6a2b60872d9f8e5d168fbc42d587f9d09bd0192b6907d923` |

其余一跳依赖归为平台 ports：AIP contracts/任务/评测/模型/用量/生产合同/EffectReview、Data mapping/hydration/observation/profiling、`db`、`tenant_scope`、`auth`、`logging_facade`、`errors` 与 `public_contracts`。AR2-1 先为实际调用到的操作定义窄 `operationId + typed payload + exact ref`，不得把这些模块复制进领域包，也不得允许领域包直接导入 `aos_api`。

反向调用清册及处理方式如下；这些调用方未处理前不得删除或改写旧模块：

| reverse caller | decision / target | preHash |
|---|---|---|
| `services/aos-api/aos_api/aip_business_investigation_artifact_saga.py` | 迁入 `ecommerce_growth`，Artifact 调用改走 SDK | `b7ef4e22aaf31088dc59adb845f148435cebcae08f2c22ec6986f50ad3c0d9c4` |
| `services/aos-api/aos_api/aip_business_investigation_contribution.py` | 迁入 `ecommerce_growth` | `1257c36406b6466e942de48feb702a4ffcec365f69eaedb6ba0076d915ba9ec2` |
| `services/aos-api/aos_api/aip_business_investigation_eval.py` | 迁入 `ecommerce_growth`，Eval 调用改走 SDK | `063a12c86bca8353a5840b0a3ff8f16b7cd36d5969c0fb3f4806f3cebce85684` |
| `services/aos-api/aos_api/aip_business_investigation_evidence.py` | 迁入 `ecommerce_growth`，Evidence 调用改走 SDK | `0764a1bb934568b76bf72b940b147e3a156d3428eb7e4fc619290553ae044aec` |
| `services/aos-api/aos_api/aip_business_investigation_fulfillment_saga.py` | 迁入 `ecommerce_growth`，DataRequirement/Fulfillment 改走 SDK | `b5a1c79cc4aeba66265429296bcb8b3d3b4659e67866ff163c7ae98465fbc36d` |
| `services/aos-api/aos_api/aip_business_investigation_reconcile_saga.py` | 迁入 `ecommerce_growth` | `0864f624768f65bd29b893662fca6d51b4981dec3b089c228587a460282c5837` |
| `services/aos-api/aos_api/aip_business_investigation_research.py` | 迁入 `ecommerce_growth` | `deb328355839faa141624581e89b45425b771de7707684096f0a001de60528b7` |
| `services/aos-api/aos_api/ecommerce_analyst_materializer.py` | 迁入 `ecommerce_growth` | `e992f722a94c8f0f048ad1822ea359a95aca50cdef4ccb58429cfe7f5c8924fd` |
| `services/aos-api/aos_api/ecommerce_business_investigation_aip_composition.py` | 迁入 `ecommerce_growth`，公共组合通过 SDK 注入 | `45d6f12f839501a6179a1c1364d2031a417138b3b4f33b38945b7b8399b298a6` |
| `services/aos-api/aos_api/ecommerce_business_investigation_artifact.py` | 迁入 `ecommerce_growth` | `6fc11dfee4acea6a2216a113b034f88d8120c80e6bea5faf1df779a01f78b102` |
| `services/aos-api/aos_api/ecommerce_business_investigation_artifact_publication.py` | 迁入 `ecommerce_growth`，发布仅内部 Artifact authority | `f48b3260f7b88b0ec0bce7f9b5bbb0afcedfa95fbce363009f4779d30208674f` |
| `services/aos-api/aos_api/ecommerce_business_investigation_profile_catalog.py` | 迁入 `ecommerce_growth` | `88f81c0c206f69144a0709bb3af566543cb2bdc43686273fcecb34e8ced376d2` |
| `services/aos-api/aos_api/aip_handoff_reference_authority.py` | 留平台；移除对 cockpit 实现导入，只消费通用 Handoff/ExactRef port | `713d48b7ff8984563149f894037a6fc4b619f20181e7279e4fe037b3a84173b9` |
| `services/aos-api/aos_api/routers/ecommerce_business_investigations.py` | AR2 切换前保留；切换时原子改为 Canonical installation dispatch，旧实现不再可写 | `ef63dde1f0207982357e59af342e760dfc5ef4c8614d995514db802d2af35953` |
| `services/aos-api/aos_api/routers/ecommerce_workshop.py` | AR2 切换前保留；切换时原子改为 Canonical installation dispatch，旧实现不再可写 | `acadd20bc140699fe5008794ff69a7d625a925acaa098ef217d12f54c997e469` |
| `services/aos-api/aos_api/aip_stage_template_authority.py` | 留平台；移除对 profile catalog 实现导入，改为查询公共 Bundle/StageTemplate catalog port | `fd062cb1db3c436dcada1949d1bc19fb7765ad6b1ce2173ea9e22d153b365541` |
| `services/aos-api/aos_api/ecommerce_business_investigation_aip_readiness.py` | 迁入 `ecommerce_growth`；生产合同、绑定与技能查询经 SDK ports | `4cafb003e1bf8852baa1a4b82558cf985de8258192331dcb65ec87c59f3cac71` |
| `services/aos-api/aos_api/ecommerce_workshop_content_campaign_inputs.py` | 留 Data/Workshop 公共读取侧；移除对 campaign store 实现导入，仅消费带 cutoff 的 SDK query port 和序列化 DTO | `8fa43a446715b1fc4f939e91343fcf53c2e52da8b87e89684f199d167d550b46` |
| `services/aos-api/aos_api/ecommerce_workshop_feature_activation.py` | 留平台治理侧；FeatureActivation 权威仍由平台持有，旧 contracts 路径仅兼容转发 SDK DTO，不导入 bundle | `f5890735121be588462fcb71a9784806685fe45ff6b61fce9e84aed9199dc011` |

平台聚合与前端可达性入口同样纳入阶段合同，不能只检查 Python 领域 import：

| dynamic entry | AR2-0 baseline | AR2-1 target | AR2-7 target | preHash |
|---|---|---|---|---|
| `services/aos-api/aos_api/routers/domain_aggregates.py` | 静态聚合两个旧 Router | 保持旧入口，并登记 registration-only 的 `ecommerce_growth_dispatch` Canonical Router 壳 | 只聚合通用 `extension_dispatch` Router | `9113e28b9bb5b2a0e3462ec75d545350fcc9ab217470a69e10746b8e368b37dc` |
| `apps/web/src/App.tsx` | Workshop 通配路由进入 `EcommerceWorkshopEntryRoute` | 保持 | 仍仅进入通用宿主入口，不静态识别八页实现 | `b923a9a3b1540cdec71e16399964a9257be4d712e2481ec8f66f11c8122a2aa7` |
| `apps/web/src/pages/s2/ecommerce/routes.tsx` | 订单/库存保留静态 LegacyFallback | 保持旧读页，骨架期不切业务 | 删除静态 LegacyFallback，旧 URL 作为安装声明别名只进入 `EcommerceWorkshopHost`；未安装不可执行 | `043860b4796298c02c89b41724ca2c96b126fef5b09c26069cd7a2187e0882e1` |
| `apps/web/src/components/workshop/InstalledModuleNavigation.tsx` | 无论安装与否都展开八个 `WORKSHOP_ACCEPTANCE_MODULES` | 保持，等待最终切换 | 菜单仅消费当前安装、角色/权限允许的 catalog slots；未安装模块不渲染、不执行 | `700cb9f6d616a826577fe0070bc6434182be0c76aadfe35f5d10521ce000f2af` |

动态期望保存在同目录 `dynamic-reference-phases.json`，验证器必须显式接受 `--phase ar2-0|ar2-1|ar2-7`。AR2-0 校验冻结哈希；AR2-1 校验三包 backend/运行声明且旧入口未提前切换；AR2-7 校验平台只注册通用 Router、页面仅进入通用宿主、八菜单只来自安装与权限后的 slots。这样正确施工不会被旧基线误报，同时任何静态旁路回归都会确定性失败。

固定点退出规则不是固定数量：以所有标记“迁入”的模块为集合 `M`，反复执行“展开 `M` 对 `aos_api.*` 的正向领域依赖；全仓搜索对 `M` 的反向导入”；每个新节点必须登记为 `迁入 / 公共 port / DTO 兼容转发` 之一并保存 preHash，再进入下一轮。只有一轮扫描产生零个未分类领域节点才允许结束 AR2-0。当前扫描已把上述 5 个新增正向节点和 4 个新增反向调用方分类；`business_investigation_hydration.py` 与 `business_investigation_shared_contracts.py` 已在本节定义为公共 port/SDK 拆分。再次扫描的剩余边只落到已登记节点或 `db`、租户、鉴权、AIP 生产合同等公共平台 ports，因此当前集合达到固定点。AR2-1 每次新增迁移节点都必须重跑同一规则，出现新节点即回开清册，禁止以行数或文件数替代闭包。

仍使用 `business_investigation_shared_contracts` 的平台 Data 模块在 AR2 通过旧路径兼容转发到公共 SDK 的通用 ExactRef/信封，不能从平台进程 import bundle；电商专有 DTO 仅通过序列化 schema 与 core 包对齐。该兼容层不持有执行权。微信小店、抖店 Adapter 的完整物理迁移留在 BI-W9/AR3，但不得由它们取得 growth 的写入口。

## 4. AR2 串行子包与验收单位

| 子包 | 内容 | 可验证退出条件 | 下一项 |
|---|---|---|---|
| AR2-0 | 本清册、动态引用和 preHash 冻结 | 25 个种子、19 个追加迁移依赖及全部已扫描反向调用方均有唯一处理方式；固定点扫描零未分类领域节点；静态 Router/主进程引用已列出 | AR2-1 |
| AR2-1 | core/growth/niushop 后端骨架、注册入口、SDK ports、manifest runtime | 包能独立构建注册；不导入 `aos_api` 私有模块 | AR2-2 |
| AR2-2 | N1 Case/Schedule 与 N2 occurrence/outbox/dispatcher | 唯一自然槽位产生唯一 occurrence，并路由到当前安装 | AR2-3 |
| AR2-3 | N3 Niushop connector、DataRequirement/Fulfillment | 隔离 fixture 产生同截止真实形状的 Fact/Evidence；跨租户拒绝 | AR2-4 |
| AR2-4 | N4 编译/运行/Data Saga | occurrence 形成可恢复 Run/Plan/TaskRun，不以 PREPARING 算完成 | AR2-5 |
| AR2-5 | N5/N6 评审、Handoff、内容任务承接 | exact 批准自动续跑并产生唯一内部 Task/Brief | AR2-6 |
| AR2-6 | N7 预算预留、能力调用边界、Usage 对账 | 不调用真实 Provider；隔离执行覆盖 held/released/unknown 和旧 epoch 拒绝 | AR2-7 |
| AR2-7 | N8 复盘回流、受控单写切换、包构建、装卸/重装、浏览器 | 同一 digest 完成安装、停用、卸载、重装；完整隔离链与 C01～C10 的 AR2 适用部分可点击 | A0-V |

首个纵向交付单位固定为：选择不含真实凭证与客户数据的栖月汇合同 fixture → 自然到期 occurrence → Case/Run → 同截止数据履行 → 分析建议 → exact 方案评审 → 内容内部任务 → 隔离 capability 执行与预算预留接口 → 明确标记为隔离证据的可读 Artifact → 内容人工评审 → 批准事件自动续跑 → 总控复盘与 Wiki 候选回读。AR2 不调用真实 Provider、不产生真实费用，也不把 fixture 或隔离产物写成真实经营结果；A0-V/A1 在相同包 digest 上通过当前授权读取栖月汇真实只读数据并调用获准能力。

## 5. 单写切换状态机

AR2-1～AR2-6 的包 handler 允许构建、签名、注册和隔离直接测试，但没有虚构的 `shadow_disabled` 状态：精确映射为现有 `extension_runtime_binding.enabled=false + operation_fence=true`，此时 `effective_ready=false`，允许动作仅为构建、注册、配置、隔离测试和卸载，禁止任何 Canonical 业务派发；“注册成功”绝不等于业务激活。

AR2-1 新增通用持久权威 `extension_operation_dispatch_binding`（仅迁移代码和测试，不在 AR2 擅自执行共享迁移），字段至少为 `org_id/project_id/operation_id` 主键、`handler_kind`（`legacy|extension`）、nullable `installation_id/generation`、`execution_epoch`、`operation_fence`、`revision`、`cutover_group_id/cutover_group_revision`、`updated_at/updated_by`。所有经营参谋 HTTP 命令与 occurrence scheduler 必须提前部署为读取该表的通用 Router；旧实现和新 bundle handler 都只能由该 Router 通过同一指针调用，不能保留绕过入口。

Router 不跨 IPC 或远程 handler 调用持有数据库锁。它在短事务中读取 dispatch binding 与目标 runtime binding，签发不可变、不可自行扩权的 `DispatchRef(orgId, projectId, operationId, handlerKind, dispatchRevision, installationId, generation, executionEpoch, cutoverGroupId, cutoverGroupRevision)`，然后释放锁并调用 handler。legacy 与 extension handler 都必须携带该引用；每个可能产生业务写入的公共 SDK port 必须在自己的提交事务内按相同锁序重新锁定 dispatch binding，逐项核对 DispatchRef 的租户、operationId、handlerKind、revision、group revision、installation/generation/epoch/fence，并复核 runtime binding。任一漂移立即拒绝写入，因此 Router 读取与最终写提交之间不存在可利用的 TOCTOU。

AR2-7 只通过数据库 CAS 切换这个 handler 指针，不再声称 Python 代码部署与数据库绑定能处于同一事务：

1. 记录旧入口 checkpoint、当前 installationId/generation/executionEpoch、policyRef、occurrence watermark 和未决 target Receipt。
2. 暂停新 occurrence claim，并将目标 runtime 从 enabled/unfenced 推进为 disabled/fenced；runtime 行锁与既有 attempt insert guard 形成线性化点，使 pause 前已启动的 attempt 可枚举、pause 后的新 attempt 被拒绝；随后排空或明确归宿旧在途命令。
3. 预先部署的通用 Router 已覆盖全部入口；一个业务链涉及的全部 operationId 先写入同一 `cutover_group_id`。在一个数据库事务内按 `org_id → project_id → cutover_group_id → operation_id（字典序）→ installation_id → generation` 固定锁序，检查组 revision、每条 dispatch `revision`、旧 `handler_kind`、旧 epoch 和目标 runtime binding revision，再整组 CAS 更新 `handler_kind=extension`、目标 installation/generation、新 epoch、`operation_fence=false`、每行 `revision+1` 及 `cutover_group_revision+1`；只要一行不匹配整组回滚，禁止半条业务链新旧分流。该事务提交点是唯一切换点。
4. 新入口每次调用携带 DispatchRef；最终公共写端口在自己的提交事务中二次核对 dispatch/runtime binding。旧 revision、旧 group revision、旧 epoch、旧批准和旧页面请求全部拒绝。
5. 切换验证失败时先以 dispatch `revision+handler_kind+epoch` 做 rollback CAS，将 dispatch fence 设为 true；排空新 epoch 后再 CAS 恢复 `handler_kind=legacy` 和旧 checkpoint。CAS 冲突一律转人工核验，不盲重试；已经接受的命令只按 target Receipt reconcile，禁止重放。

真实租户不参与 AR2 切换。AR2 数据只允许仓内合同 fixture 或经专门批准生成的脱敏隔离数据，不复制真实 `secretRef`、Cookie、客户记录或经营结果；“栖月汇”只表示 schema/映射合同兼容。真实 `org-org/dev-project` 的只读数据接入留在 A0-V/A1，并重新验证租户、SourceReadiness、预算和同一制品 digest。

## 6. AR2-0 独立复审

2026-09-07 Prime 最终结论：PASS，可封板 AR2-0 并进入 AR2-1。独立复核覆盖包内绝对/相对导入、AR2-0 专属 preHash、AR2-1 旧入口保持、AR2-7 runtime/entrypoint 继承、四根 Python 闭包和 bundle 禁止直接依赖 `aos_api`。最终命令 `verify_closure.py --phase ar2-0` 扫描 1,654 个 Python 模块，分类 64 个、迁移 44 个；hash、正向依赖、反向调用、跨层导入和动态入口错误全部为空。

## 7. 2026-09-09 接续闭包登记

原 source 列改为完整平台路径以消除迁入后同名解析歧义；第 2～3 节历史 preHash 不变。以下是接续基线 fa0612c5 已有新增节点及本次新增读取者，非 AR2-0 历史基线节点。登记不代表旧实现已经移除或 7D 已完成。

| sourcePath | target | decision | 接续基线摘要（非 AR2-0 preHash） |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` | 原路径 | platform host port；既有 AR2-7D 宿主事务适配，切换前不注册未完成服务 | 48a51c177c506b56355d4b6d14810ff471ca5feb6dd2538b32a03a3a49629727 |
| `services/aos-api/aos_api/ecommerce_growth_cutover.py` | 原路径 | platform host control port；D5 整组 prepare/commit/rollback 权威，不导入领域 bundle | 213209a8a3f000b69e22ecbc5d12933fa84ed969e50de06c2356dd9d331dc5c0 |
| `services/aos-api/aos_api/automation_occurrence_store.py` | 原路径 | platform occurrence authority；D5B 只在领取候选中读取组级 claim gate，不改变创建、结算或 UNKNOWN 对账状态机 | e708fff8502d32e93438695b8fb25834b5375577b5b4e6003f9a6aa1423c76b4 |
| `services/aos-api/aos_api/ecommerce_canonical_population.py` | 原路径 | data query port；本次新增当前规范库全集身份读取，仅由受信宿主使用 | NEW |
| `services/aos-api/aos_api/ecommerce_product_observation_comparison.py` | 原路径 | data query port；受信宿主有界商品观察与规范版本比较，不生成业务事实或履约 | NEW |
| `services/aos-api/aos_api/ecommerce_product_comparison_query.py` | 原路径 | data query port；固定比较复用MetricDefinition和QueryResult真实Owner，partial不代表履约 | NEW |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analysis_runtime.py` | 原路径 | solution package；既有包内纯编排节点；公共权威仅经 SDK ports | aebddd199ba97397b053946dee54a082c2c897ed8a80406653f5e9badc6904da |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/audit_projection.py` | 原路径 | solution package；既有包内纯编排节点；公共权威仅经 SDK ports | 8b7221e60fc6a5787dafcc0ff98ea14fc842c91fe9b5c0a07d4d63bb7b3736bc |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_artifact_review.py` | 原路径 | solution package；既有包内纯编排节点；公共权威仅经 SDK ports | d7eb9b15ee97a51b122c083ed52a70f47139f1fdcc55e8c80728b04d7921e9d2 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_capability_runtime.py` | 原路径 | solution package；既有包内纯编排节点；公共权威仅经 SDK ports | ca149ec75b9578cf2f1691db79507aa145f56b7ad73295f6e1a117ca6c687095 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/result_feedback.py` | 原路径 | solution package；既有包内纯编排节点；公共权威仅经 SDK ports | 88be9cac4f9d89a56beed20be301540481ba76c196c15f8c41d62b32bdfa12f4 |
| `bundles/platforms/ecommerce-niushop/backend/ecommerce_niushop/connector.py` | 原路径 | adapter package；既有 Niushop 类型化 connector，只由受控宿主承载读取 | 5c53d528df282609d0c2cda7bf1d848f266cf69d45933fb1fc7a49c4310db5bc |

| `services/aos-api/aos_api/ecommerce_data_requirement_query_applicability.py` | 原路径 | data query port；真实需求与固定查询只读缺口诊断，不产生履约权威 | NEW |
| `services/aos-api/aos_api/ecommerce_product_joint_quality.py` | 原路径 | data query port；验证观察后的固定逐商品联合字段计量，不产生业务事实 | NEW |
| `services/aos-api/aos_api/ecommerce_fixed_metric.py` | 原路径 | data query port；两个固定查询共用真实Metric Owner写读 | NEW |
| `services/aos-api/aos_api/ecommerce_joint_quality_query.py` | 原路径 | data query port；固定联合字段计量QueryResult持久化，partial不代表履约 | NEW |

## 8. 2026-09-10 AR2-7E 累计闭合登记

本节覆盖第 1 节的历史开工态描述。AR2-1～AR2-7D 已完成包内实现、公共 SDK ports、registration-only host ports、结果反馈恢复、Canonical Router/host composition/cutover/lifecycle 和旧 Router 单写转发；当前 authority 为 `AOS-000572`。AR2-7E 在同一 digest 与无真实凭据 fixture 边界上完成以下累计门：

- shell capability gating、页头动作 authority 与 console 预期网络错误分类均有方案、回归和验证证据；
- 八工作台入口/失败关闭矩阵 37/37 PASS；有效隔离数据矩阵 24/24 PASS，24 张截图齐备；
- 任务总控、内容计划、统一运营、达人邀约、多媒体、经营参谋、价格治理、客户运营八个富交互专项各 3/3 PASS；
- `ar2-7e-cumulative-closure.py` 对账 70 份 Git 跟踪证据、9 个产品页面哈希、三视口、租户/请求/页面/控制台错误和零副作用边界，失败集为空；
- Prime 对 `m1@e52ec81a` 做最终增量只读复核，首行 `VERDICT: PASS`。

最终 Web 测试/构建、`verify_closure.py --phase ar2-7`、共享记忆 CAS 与写后回读均已通过；Delivery Receipt 为 `AR2-HOST-WIRING-CUTOVER-PLUGGABILITY-BROWSER-ACCEPTANCE.json`，authority 已推进到 `AOS-000573`，文档提交为 `docs/palantier/m1@9239332`，总 Task Lease 已释放。

唯一退出标记：`AR2_HOST_WIRING_CUTOVER_PLUGGABILITY_BROWSER_ACCEPTANCE_GREEN`

AR2 的 fixture 证据不代表真实经营数据接入、真实 Provider、业务 mutation、230 L0、A0-V 或发布完成；下一安全阶段为 A0-V 真实授权复验。

## 9. 2026-09-11 新增分析闭包回开（迁移未完成）

基线9bab3171原扫描发现23个未分类反向调用方。本节覆盖全部新增分析邻接模块及已有合同的增量；实际源码依赖、当前摘要和目标存在性见 ../A0-V-REAL-AUTHORIZATION-REVALIDATION/analyst-package-inventory.json。历史preHash不改。以下摘要是新增接续基线，不是AR2-0历史哈希。

所有行状态为PENDING_INCREMENTAL_PACKAGE_MIGRATION；目标文件已存在也不表示当前增量已同步。登记只恢复枚举归属，**不关闭新增可插拔施工**。领域业务不得整体留宿主并重命名公共port。拆分后的宿主适配仍须提交事务内核验DispatchRef、安装代次和fence；本表不赋予运行权。

| sourcePath | targetPath | decision / 当前状态 | 接续SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_analysis_proposal.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_analysis_proposal.py` | 纯领域规则迁入 growth；私有权威依赖改用 SDK DTO/ports，尚未完成；PENDING | a82e0a5cebe1abfbeb4ef534e35377c455961a2ba2b85b4812efe4b75071bacd |
| `services/aos-api/aos_api/ecommerce_analyst_analysis_sources.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_analysis_sources.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | e3b2bec141e929e2c7aa6d69227cf7c042359be744caa1ba129c54b8bc10467a |
| `services/aos-api/aos_api/ecommerce_analyst_authority_contracts.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_authority_contracts.py` | 领域 DTO 迁入 growth；平台仅保留版本化 DTO 兼容转发，尚未完成增量同步；PENDING | d069b6b4339edc16f7c8644c3fbb538edc24683a798cfd93a7bba3d3c7b3722a |
| `services/aos-api/aos_api/ecommerce_analyst_authority_store.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_authority_store.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | a93a904abee9a9b500ae57dd35fd32c2c6d07de4ca5abfa12a8883d4861560a2 |
| `services/aos-api/aos_api/ecommerce_analyst_diagnosis_generation.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_diagnosis_generation.py` | 纯领域规则迁入 growth；私有权威依赖改用 SDK DTO/ports，尚未完成；PENDING | 89b8faee6376a0ea02c4ddab100c36bdae90feeafa4eb524130720901540b340 |
| `services/aos-api/aos_api/ecommerce_analyst_diagnosis_receiver.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_diagnosis_receiver.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 97360fe51c48e3a51e0174e8be643722f8d23b9fde6f339dc1d7e4e39c8fde84 |
| `services/aos-api/aos_api/ecommerce_analyst_diagnosis_service.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_diagnosis_service.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | e3a593a18c52183d2e6cea8221ca56d2d7587a0414b3a66e9e8e42022be43a57 |
| `services/aos-api/aos_api/ecommerce_analyst_diagnosis_worker.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_diagnosis_worker.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 2618041c6a23ee9a39988c724d533c1556993af9b4cfe56353a7a083b2521a1f |
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_approval.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_approval.py` | 纯领域规则迁入 growth；私有权威依赖改用 SDK DTO/ports，尚未完成；PENDING | 9d3013da2cfb7f78bc5075183a986155a5515a3ecb24e02abed35ec42b834728 |
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_draft.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_draft.py` | 纯领域规则迁入 growth；私有权威依赖改用 SDK DTO/ports，尚未完成；PENDING | efd1efa8ed85605f9bceb61e3e092e8932bc962bde8ed2e5746b259652840271 |
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_generation.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_generation.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | d0efab091d904f9bf016e74e0f183cb5cbbe6e259dabd767312f0dd72ce03e39 |
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_receiver.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_receiver.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 8c5ae5598a08fbb24fd9caba6fbdb28007e7bf4e9e0920039e871edece5d6ffa |
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_sources.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_sources.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 7fa6125be35a312c5c4ecded4777a404014e145534ef467e51fb043bf435b99c |
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_worker.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_worker.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 0d9b35064d469ce5a8baefbe9910ed6a90b09334e8bfa268376cde4b259cb59d |
| `services/aos-api/aos_api/ecommerce_analyst_materializer.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_materializer.py` | 纯领域规则迁入 growth；私有权威依赖改用 SDK DTO/ports，尚未完成；PENDING | e992f722a94c8f0f048ad1822ea359a95aca50cdef4ccb58429cfe7f5c8924fd |
| `services/aos-api/aos_api/ecommerce_analyst_portrait_generation.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_portrait_generation.py` | 纯领域规则迁入 growth；私有权威依赖改用 SDK DTO/ports，尚未完成；PENDING | 18ead3a5c49f146e3c97c25146a948a594de86230b85e7b7d258b7e1e9d11eb8 |
| `services/aos-api/aos_api/ecommerce_analyst_portrait_inputs.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_portrait_inputs.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 7dfe12d419643974e8ca48da8e6160ed76a12124495e372715648963edd8d01e |
| `services/aos-api/aos_api/ecommerce_analyst_portrait_method.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_portrait_method.py` | 纯领域规则迁入 growth；私有权威依赖改用 SDK DTO/ports，尚未完成；PENDING | 98d8ef0c8f65748f3427c7febeb775bfb576c924cf243ea41911af3a183e2247 |
| `services/aos-api/aos_api/ecommerce_analyst_portrait_query_sources.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_portrait_query_sources.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | d3f26f8b522e8596b77e79bf4d46e04b630dbad006db072ff6b4d7adf2f72bb6 |
| `services/aos-api/aos_api/ecommerce_analyst_portrait_receiver.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_portrait_receiver.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 898c8f854de97a40cf26cb60bcc4f1bd0492fa0f26a61543c1afab87450f5671 |
| `services/aos-api/aos_api/ecommerce_analyst_portrait_service.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_portrait_service.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 501b2ae364f967b9dadc2333c2c302e21d9e97e80b9f8421fcd1cbcb0ddaf8bb |
| `services/aos-api/aos_api/ecommerce_analyst_portrait_sources.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_portrait_sources.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 2d3069016b381322fd3fb6558287d879a54dad9bbf5a998271872f955d5f9259 |
| `services/aos-api/aos_api/ecommerce_analyst_portrait_worker.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_portrait_worker.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | ba5f1f79418ef6e196bbe642c4b4df25232ea6e0f0b268db37afe34780040da9 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_decision.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_decision.py` | 领域 DTO 迁入 growth；平台仅保留版本化 DTO 兼容转发，尚未完成增量同步；PENDING | 2682979a24abeaba6625f983599eeb4e6a2064723a45476a0f50ea9594e1aaf4 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_decision_store.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_decision_store.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | eba8988bc7c7d2618ad4ff4891b2f91533bc78c2db585dbcd6765e7b4f6e07df |
| `services/aos-api/aos_api/ecommerce_analyst_stage_eval_report.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_eval_report.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 42738a811ca13568d79b60a73a20af7304bf4f758a43c71930a3b1e49d57d731 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_authority.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_authority.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 1e549eaca433462b9ea807241dfd98443e5f1b0f46940caf9f89c022638f7186 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_command.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | a1fb256df668f69ae3db3d43fc71df816660cd399476e183e62506e975ddfd4d |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_runtime.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_runtime.py` | 拆分：领域规则迁入 growth；通用权威读取/事务/执行留宿主公共 port，尚未拆分；PENDING | 6e8bd4e0bb827e550e97c7fbc15a38f8531da6cfe529e020c1b342ade4d4bf36 |

### 9.1 无权威回答DTO切片

2026-09-11：以下两个包文件现在只拥有D01/D02/D03严格回答解析。平台仍通过原路径提供兼容DTO，以schema/正负样例验证对齐，不从平台import bundle。growth_plan_draft的提示词、实际生成、接收事务和后继编排仍未迁移，故第9节29项整体PENDING不变。inventory.json是9bab3171冻结快照，不覆盖历史targetExists；本节才是新目标存在性证据。没有新增运行operation或安装激活。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_analysis_proposal.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_analysis_proposal.py` | DTO解析切片迁入 growth；执行编排仍PENDING | 4a4316fa1f4f7f4532148fbe3bcae9e19b68988c1cb22ef6143a69681e44ca0e |
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_draft.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_draft.py` | DTO解析切片迁入 growth；执行编排仍PENDING | 74129df3c3ea51a0a9632984b1d26124c4c5fdda8e17bbcdf256c0718541221c |

| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analyst_structure_eval.py` | 原路径 | growth纯结构评估；无权威、无运行注册，联合运行仍PENDING | ca60642772cd52e4b18715940d9f907f36171ef5bc6dec1cc6562dbe1e85122b |

| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analyst_structure_case.py` | 原路径 | growth纯生成输入到结构规则转换；来源Owner与运行装配仍PENDING | 1c903f9e7781d1952d38c3847a670ee329e95a08bf8f9db205b8111471217109 |

### 9.2 分析来源材料合同切片

2026-09-11：`ecommerce_analyst_analysis_sources.py` 的纯请求/材料合同与二次完整性校验迁入 growth 包。宿主继续唯一拥有 TenantScope、TaskBrief、EvidenceBundle、Disclosure、freshness、revocation、marking、事务和数据库读取；本切片不修改宿主旧文件，不注册运行 operation。

包校验 exact bundle/evidence refs、同 Task 且不重复的 grant 集合、材料全量覆盖、宿主权威顺序保留、Disclosure identity/expiry、payload 原文 hash、cutoff 和总字节上限。grants 明确为无序授权集合，不能重排宿主返回的 EvidenceBundle 项。运行 target、原始 Attempt query 绑定和宿主 source port 仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_analysis_sources.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_analysis_sources.py` | 纯合同/材料校验迁入 growth；宿主 Owner 读取与事务 port 仍 PENDING | c9b546c3b61d79694e39b0cfc821c4fa7e098d7e648208746b8b6fb7e2998583 |

### 9.3 分析来源宿主端口切片

2026-09-11：growth 包通过 `GrowthAnalysisSourcePort` 单次读取由宿主授权的分析材料，
随后执行 9.2 的二次完整性校验。宿主端口在构造时绑定 `TenantScope` 与
`HostTransaction`，调用方不能传入或覆盖租户，包不能获得原始数据库连接。既有宿主
Owner 继续唯一裁决 TaskBrief、EvidenceBundle、Disclosure、freshness、revocation 与
marking。本切片只读，不增加公开路由、operation 注册、Provider 或 Receipt。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_analysis_source_port.py` | 原路径 | platform host port；绑定租户和窄事务后调用既有 Owner 读取，不进入领域包 | 2c3d65ac64cfeb062e3c7a92a3636a93f4d9d444745930fe73c45a8be863d616 |
| `services/aos-api/aos_api/ecommerce_analyst_analysis_sources.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_analysis_sources.py` | 包端单次读取编排与二次校验完成；成功 Attempt query、Artifact 和正式 Eval target 装配仍 PENDING | d79357fc1aacf96889b76fc0508ffc54b7c15eeabc19ce34904f9c5e7f91fc4a |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/sdk_ports.py` | 原路径 | solution package 公共 SDK；新增租户绑定的只读 GrowthAnalysisSourcePort | c36cda9fdbfcae6bbea1915ae7ee70ae0f8f5b00cbf008ca87694967c84b9cdb |

### 9.4 正式 Eval 目标绑定切片

2026-09-11：阶段人工评审在同一宿主事务内，从已经核验的成功 AgentRun 请求派生 exact
SkillTemplate target，并要求 passed Eval report.target 的类型、ID、revision、contentHash
完全一致。合同 Suite、release gate、原始文字 Artifact、AgentRun Attempt、租户与时序的
既有校验继续生效。该切片不创建 Eval、不发布 Skill、不调用 Provider。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_command.py` | 宿主阶段评审新增 exact Skill Eval target 防替换校验；包内编排迁移仍 PENDING | ca5b442e0886b5bf31a6b6da0f2d89628a000470cbae274e08afb95167e4b999 |

### 9.5 AgentRun 原始 Query 私有 Owner

2026-09-11：新增租户隔离、append-only 的 `aip_agent_query_input`，将原始 query 正文与
exact Artifact、AgentRun Attempt、requestHash、contentHash 和 marking 同时绑定。正文
不进入通用 Artifact metadata、Receipt、日志或 Eval report。`AipTaskStore` 仅为明确的
`agent_query_input` 类型调用该 Owner；既有输出正文路径保持不变。

该切片只建立 Owner 和原子 Artifact 写入能力，尚未默认留存模型输入，也未接入
D01/D02/D03 生成或 Eval case；不调用 Provider、不产生业务 mutation。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/aip_agent_query_input.py` | 原路径 | platform private source owner；原始 query 受租户、Attempt、requestHash 与 marking 约束 | 58552c531d35a1f754d77396e40f3611624c669d15d27de2880b410507642ccf |
| `services/aos-api/aos_api/aip_task_store.py` | 原路径 | platform Artifact owner；新增 agent_query_input 私有正文分派，既有路径保持 | 56e59616c566bd8c1e1d07904c7076970e195809fcae915b1d59255e6a4c6b9f |

### 9.6 AgentRun Query 执行期留存切片

2026-09-11：明确开启正文留存的受治理 AgentRun executor，在 Attempt 仍为 PREPARED 且
Provider 尚未调用时，先写确定性的 `agent_query_input` Artifact。写入绑定 tenant、TaskRun、
AgentRun、Attempt、requestHash、query contentHash 与 marking；正文仅交给 9.5 私有 Owner，
不进入通用 Artifact metadata、Receipt 或日志。输入写入失败时 Attempt/AgentRun 收口为
FAILED，Provider 调用数必须为零。默认 executor 仍不留存输入正文。

输出 Artifact source 同步携带 Attempt requestHash，供后继 Eval case 对 query/output/Skill
做同源核验。本切片不创建 Eval、不启动真实业务运行，也不扩大 Provider、预算或审批权限。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/aip_agent_run_executor.py` | 原路径 | platform 受治理执行编排；显式模式 Provider 前留存 query，失败零 Provider 副作用；后继 Eval case 装配仍 PENDING | f5dcb41673ec1802d9cddedc3aa3acd5ac88f53071845b9e25f4687994e6a48d |

### 9.7 经营参谋正式 Eval case 同源绑定切片

2026-09-11：阶段评审在同一宿主事务内，要求 output Artifact source 与成功 Attempt 的
agentRunId、attemptId、requestHash 完全一致，并定位该 Attempt 唯一的 `agent_query_input`。
query 经私有 Owner 按当前 markings 回读，再交给显式注入的已安装 growth 包纯函数按 stage
派生结构 case；平台不反向 import 包，也不接受评审调用方自报 case。

当前 EvalContract 所指 exact Suite 必须以 AgentRun request 的 exact SkillTemplate 为 target，
且只含一条 required positive case；输入/期望 Artifact 类型、revision、派生 case hash 和报告
caseId 全部匹配才允许阶段决定。历史无 query Artifact 的 Attempt fail closed。本切片不创建
Suite、Eval、报告或 release gate，可信运行时函数装配仍是下一切片。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_command.py` | 宿主评审绑定私有 query、包派生 case、exact Suite/Skill/report；包内运行时装配仍 PENDING | 2c42badebac8822fb161cb40d86dcc0d9b0228570c9c606152db947789dc8372 |

### 9.8 Growth 包结构 case 纯运行 operation

2026-09-11：growth 作者树复用已声明的 `ecommerce_growth_analysis_advance` operation，只对
严格的 `derive_structure_case` 消息开放包内纯函数。payload 必须恰好包含 `kind/query/stage`；
query 与 stage 继续由包内规则校验。返回值只有结构 case，不回传原始 query，也不读取租户、
数据库、安装、权限、预算或凭据。其他消息与其他已注册 operation 继续 registration-only，
未知 operation 继续拒绝。

已 canonical publish 且属于 approved Installation 的 `solution.ecommerce.growth@1.4.0` 未修改。
因此本节证明作者包具备可装配入口，不证明当前 Installation 已获得该实现。下一步先复核本节
其余 PENDING 边界，闭合后冻结新的 1.5.0 Candidate、OCI/签名和 successor install。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py` | 原路径 | 严格消息路由到包内结构派生；无外部副作用，当前安装装配仍 PENDING | ce22b4f702ca4bd82163ac1fa973ae86e2ced13349cbb4454b1f2e90de296266 |
| `services/aos-api/tests/extension_runtime/test_analyst_structure_runtime_operation.py` | 原路径 | 三阶段正例、严格 envelope、无正文返回及其余 operation 拒绝合同 | 282ff5396923668eb2399b2ae4da65e428340962f67532829dd6fbf7b96b8537 |

### 9.9 经营参谋权威领域 DTO 根包化

2026-09-12：新增 growth 包内独立 `ecommerce_analyst_authority_contracts.py`，完整承载
AnalystExactRef、Method、Insight、Decision、GrowthPlan、TaskGraph、EffectReview 和 Receipt
的版本化 DTO 与校验规则。包文件只依赖 Python/Pydantic；TenantContext 仅是响应/证据上下文，
请求携带它不能授权访问。平台旧路径保持不变，包/宿主所有公开模型由 JSON Schema parity 和
代表性序列化 parity 约束，禁止两个合同静默分叉。

本切片没有迁移 Store、事务、TenantScope、Task/Artifact/Eval Owner，没有注册运行 operation，
也没有修改 Candidate、OCI、Registry 或 Installation。第 9 节 29 项整体仍为增量迁移 PENDING；
后续纯领域规则可依赖此包内 DTO 根，混合模块仍须拆为包内编排与宿主窄端口。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_authority_contracts.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_authority_contracts.py` | 全量领域 DTO/schema 迁入；平台保留不依赖包的版本兼容路径，运行装配仍 PENDING | f1b25967829edd0a597f2a7b713f59ee3a42f25b2c043b3bb2cbabcd571675b0 |
| `services/aos-api/tests/extension_runtime/test_analyst_authority_contracts_package.py` | 原路径 | 全模型 schema、关键序列化、负向校验与独立 import 合同 | 45dfd841a176189a62301f52a84e470dae38eb66d506aa858e0fb3a8748a86af |

### 9.10 经营计划审批 successor 纯规则

2026-09-12：growth 包新增无存储的 `approve_growth_plan_successor`。它要求 draft 与 exact ref
的类型、ID、revision、contentHash 一致，path、If-Match 版本、宿主已核验 current 标记、规范
actor 和带时区审批时间全部有效，才生成 revision/version 相邻的 APPROVED successor，绑定
priorRef 并重算规范 contentHash。输出仍只是一份待宿主持久化的领域对象，不允许外部效果。

幂等 Receipt、当前头、调用身份、并发 CAS 和 publish 继续由宿主 Store 在事务内裁决。宿主
旧 Service 未修改，合法转换结果由 parity 测试约束。当前 Candidate、OCI、Registry、Installation
均未改变；第 9 节整体仍 PENDING，后续还需窄写端口和可信运行装配。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_approval.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_approval.py` | DRAFT→APPROVED 纯状态转换迁入；receipt-first 宿主事务与运行装配仍 PENDING | 89f4afe1633b5e298a2fd8cd2eeaf3d8cd9d07c9100ac02394a30233780e81f2 |
| `services/aos-api/tests/extension_runtime/test_analyst_growth_plan_approval_rule.py` | 原路径 | 宿主合法结果 parity、exact/版本/状态/actor/时间负向边界与隔离 import | 98708bd1a6d0983bb9d22bc3d36ae165a85286e0f9ea57b7e48e979806a41d26 |

### 9.11 经营计划到 TaskGraph 纯展开规则

2026-09-12：审计确认 GrowthPlan 批准继续由认证 Principal 发起的唯一宿主 HTTP API 承担；
现有 Store 已在一次事务中完成 Receipt-first、head lock、expectedVersion、CAS、revision 与 Receipt
写入，因此不新增 extension 发起的第二审批端口。

growth 包新增 `build_canonical_task_requests` 与 `assemble_task_graph`：先核验 approved plan 和
exact planRef，只按原顺序展开 eligible item；宿主 Task Owner 返回完整且仅包含 exact Task ref
的映射后，才组装数量守恒、一对一并按现行算法计算 hash 的 TaskGraphRevision。包不判断当前
head，不创建 Task，不发布图，也不读写数据库或 Receipt。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_materializer.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_materializer.py` | eligible Task 请求与完整 TaskGraph 纯展开迁入；current、Task/图 Owner、事务和运行装配仍 PENDING | 189612b5c630608c68a7ba43bd31b7b7f212506d5fa5fff5c9931da1b8c48b25 |
| `services/aos-api/tests/extension_runtime/test_analyst_materializer_rule.py` | 原路径 | 宿主合法结果 parity、映射/引用/状态/时间负向合同与隔离 import | 7ec1676274b9bfe068892248a8dbc083eb59f5f40a9d5fef4ab33a0f121e3cf0 |

### 9.12 exact 人工阶段决定领域合同

2026-09-12：growth 包新增独立 AnalystStageDecisionRevision、EvalStageAttemptRef 和
AssigneeRef/AssigneeKind 值合同，JSON Schema 与宿主完全一致；同时迁入仅比较宿主已核验当前
决定的适用性规则。portrait、diagnosis、solution-design 分别只接受对应 subject 类型，reviewer
必须是与 createdBy 相同的 human_principal，accept 必须有不超过七天的显式有效期。

TenantContext 只参与相等比较，不能成为请求授权；当前决定、人工身份、角色、租户、TaskRun、
EvalReport、ResponsibilityPlan 的读取与发布事务仍归宿主 Owner。包不读取数据库、不注册
operation、不创建 Handoff。当前 1.4.0 安装未改变，第 9 节整体仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_decision.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_decision.py` | 阶段决定 DTO 与无权威适用性比较迁入；当前决定 Owner、运行/评审权威和装配仍 PENDING | 43911d6d7b1255a81d592f6803bff5df48b778688c5513e4876cecc3bda7c352 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_decision_package.py` | 原路径 | 全 schema、三阶段序列化、适用性/替换/布尔版本负向与隔离 import | 3a033f9921b86be396581f582f65ddcb8654644f042de6e998901401c3f67bbc |

### 9.13 人工阶段评审职责槽纯规则

2026-09-12：审计确认 `AnalystStageDecisionStore` 必须继续留在宿主：它绑定
HostTransaction 与 TenantScope，并在同一事务中完成 advisory lock、Receipt-first、head CAS、
相邻 revision、事务时钟、不可变历史和租户隔离。包不得直接获得数据库或用另一写端口绕过
这条单写者路径。

growth 包新增 `require_stage_review_slot`，只核对由宿主当前 ResponsibilityPlan Owner 已验证并
投影出的职责槽值。三个阶段必须各自命中唯一命名规则；槽必须是 independent_review，回退到
同一阶段，requiredCapabilityIds 为严格空列表，assignee 是 actor 本人的 human_principal v1，
且解析 Receipt ID 规范非空。布尔 version、额外 capability、字段替换和超长 Receipt ID 均拒绝。

成员资格、计划 current/hash/lifecycle/readiness/coverage、Receipt 存在与有效期、snapshot/content
hash、exact selection 和 bundle version lock 仍由宿主在锁内复核。本切片不读取数据库、不注册
operation、不修改 Candidate、OCI、Registry 或 Installation；当前 1.4.0 安装未改变，第 9 节
整体仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_authority.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_authority.py` | 职责槽纯匹配规则迁入；计划/成员/Receipt/current/事务 Owner 和运行装配仍 PENDING | 3af9697c38a94d544510aed0458e18763ae6af563d21c31097365c57c75b7462 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_slot_rule.py` | 原路径 | 三阶段 parity、字段/身份/布尔版本负向边界与隔离 import | fb141b72c902bed0883772585136e867b3d1e0d948ae6a4274501a5616717bd2 |

### 9.14 阶段评审命令身份纯规则

2026-09-12：审计确认阶段评审 command 的私有 query、AgentRun、Artifact、Eval Suite/Gate/Report、
责任计划、人工权限、安装运行时、事务锁、幂等 Receipt 和 StageDecision Store 发布均属于宿主。
现有产品也没有自动替人生成 accept/return/reject/revoke 的规则，本切片不发明自动评审。

growth 包新增与宿主一致的 `stage_decision_id` 和 `require_stage_review_command_identity`。稳定 ID
绑定 tenant、TaskRun、Plan、stage、StepRunAttempt、subject、Artifact 与 EvalReport；提议决定
还必须匹配期望 tenant、规范 actor、规范幂等 key、严格非负 expectedVersion、自身 ID 和规范
contentHash。ResponsibilityPlan 是决定正文的 exact 字段并受 contentHash 保护，依照现行宿主
合同不参与稳定目标 ID，从而允许同一评审目标的职责计划迭代仍归于同一决定链。

该函数只验证值身份，不认证 actor，不证明 current/prior/Eval/责任计划有效，也不写 Receipt 或
数据库。宿主仍在同一事务中完成全部当前性与副作用裁决。当前 1.4.0 安装未改变，第 9 节整体
仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_command.py` | 稳定 decisionId 与命令身份校验迁入；来源/Eval/权限/事务/Receipt/Store 和运行装配仍 PENDING | 5ece350a645d0a9269c48efb970079a9d0590f104545ebb256bdfc6ab2222206 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_command_identity.py` | 原路径 | 三阶段宿主算法 parity、身份/hash/布尔版本负向边界与隔离 import | 0ed0fe2849a011455bb516edd527021a6acab50b6926169a74b3896ec952621a |

### 9.15 阶段评审运行 exact 纯规则

2026-09-12：审计确认 stage review runtime 对当前 Task/Plan/Run、最新 StepRun、Checkpoint、
依赖快照和 Evidence 的读取，以及状态机、撤销与内容 hash 校验，均是宿主权威，不进入包。

growth 包新增 `require_stage_runtime_references` 与 `require_observed_stage_subject`。前者固定三个阶段
的 PlanRevision、同 TaskRun 的 exact StepRunAttempt 和对应 subject 类型，并要求 runtime stepKey
使用精确阶段拼写；后者只在宿主已验证 Evidence 当前、未撤销且正文 hash 正确之后，核对正文
绑定同一 stepRun、stage 和 exact `insightRef`/`decisionRef`/`growthPlanRef`。

包函数不判断 Run/Task/Plan current、step 状态与顺序、inputHash、Checkpoint、依赖快照、Evidence
hash/revocation/marking，也不访问 TenantScope 或数据库。当前 1.4.0 安装未改变，第 9 节整体仍
PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_runtime.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_runtime.py` | exact 引用与已验真观察正文比较迁入；Task/Plan/Run/Step/Checkpoint/Evidence Owner 和装配仍 PENDING | cf0055eb757adc7100c6f3a67a6bd5cefbc59090656b50751d38441b7154a477 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_runtime_rule.py` | 原路径 | 三阶段正例、引用/拼写/观察漂移和隔离 import 合同 | 9b93c2cd59731a5c7074b932446b44aa8f6640a7bf078f5f7a55f19f4b94bf10 |

### 9.16 阶段 Eval 报告最小证明

2026-09-12：平台通用 EvalReportRevision 继续唯一拥有完整 Suite、target、dataset、judge、results
合同；growth 包不复制该平台类型。包新增最小 `StageEvalReportProof`，只承载阶段评审所需的 report
exact ref、EvalContract、subject Artifact、StepRunAttempt、GatePolicy、cutoff、gatePassed 和
createdAt，并由 `require_stage_eval_report_inputs` 核对可信 now、passed/时间和五项 exact 输入。

完整报告与原始行 hash、latest、EvalRun 成功与执行时序、Suite/Gate 当前性、TenantScope 和数据库
仍归宿主。本切片不授予评审或执行权限，不修改当前 1.4.0 安装；第 9 节整体仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_eval_report.py` | `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_eval_report.py` | 最小证明 DTO 与 exact 输入比较迁入；完整 Report/Run/Suite/Gate Owner 和装配仍 PENDING | 09330f7238ddc238b69c0a7349cb58bd3624794a5258580f836d39b0da7af367 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_eval_report_proof.py` | 原路径 | passed/时间/五项绑定/布尔版本负向与隔离 import 合同 | 65f551c5e0353c0b9b75ed36ebd71fb4f9f7176d09e0debad3ee7db9a07f75c6 |

### 9.17 阶段评审包侧 review operation

2026-09-12：作者树既有 `ecommerce_growth_review_advance` 由 registration-only 扩展为四类严格
无副作用消息：command identity、review slot、runtime exact/observation、Eval proof。dispatcher
要求每类 payload 键集合完全一致，复用 9.13—9.16 纯规则，只返回最小 decision/assignee/
subject/report 引用。空 payload、未知 kind 和额外字段继续拒绝；既有 analysis derive 不变。

该 operation 不读取数据库、不认证 Principal、不判断 current/latest、不写 Receipt 或决定、不调用
Provider。当前 1.4.0 不含本实现，宿主后续必须经安装 runtime IPC 调用，禁止直接 import 作者树；
1.5.0 Candidate 与 successor Installation 仍待清册边界闭合。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py` | 原路径 | review operation 严格路由；当前安装未变化 | 5aa2430e7bf976c91bc0b45a45b0016d9869b5632069df7229ee1645ace4a403 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analyst_stage_review_runtime_operation.py` | 原路径 | 四类无副作用评审消息 dispatcher；宿主 IPC 适配仍 PENDING | db4bc5a5fc892e7cf67a310dd7426132094605acd57d73b205c6c35e5e9e93cd |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_runtime_operation.py` | 原路径 | 四消息、严格 envelope 与未知消息拒绝合同 | f1d763b641a7e6a722e63992a1068d52cf79e7430a501c07a0f7057f9f5d0427 |

### 9.18 已安装阶段评审单次调用端口

2026-09-12：新增宿主异步 `InstalledGrowthStageReviewPort`，只接受 9.17 四种 kind 的原生 JSON
payload 与显式 expected response，固定调用 `ecommerce_growth_review_advance`，每次恰好 await 一次
已安装会话调用。返回必须是原生 JSON 对象并与 expected exact 相等。

旧 1.4.0 PermissionError、超时未知、取消和其他异常全部原样上抛，禁止重发或回退作者树。端口不
发现 Installation、不缓存权限、不持有 TenantScope 或事务。同步 StageReviewCommand 的事务分段
仍 PENDING，当前安装未变化。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_package_port.py` | 原路径 | host one-shot installed runtime transport；事务编排与安装选择仍 PENDING | fcd9d0238120a80209c0a247b4cfd924e3b4188dff4fc02ce06926c0254ad758 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_installed_port.py` | 原路径 | 四 kind、exact response、非 JSON、异常/取消零重试合同 | 4b86ee3d1c1651eb30000cf830729429020da6bd51544f25b7fd5a9891b0fa19 |

### 9.19 阶段评审三段式无重试协调器

2026-09-12：新增 `AsyncStageReviewCommandCoordinator` 与不可变 prepared/exchange 快照。宿主
prepare 必须绑定原命令 canonical hash，并提供一至四个 kind 唯一的 payload/expected；协调器
逐个调用 9.18 one-shot port，在调用前后复核快照 hash，最后仅调用 commit 一次。

prepare hash 错、IPC 拒绝/超时/取消/响应漂移、调用中 payload 篡改和 commit 失败均立即停止，
不重放先前 IPC。协调器不访问数据库、不写 Receipt；commit 的新事务 current 重验证适配仍
PENDING，当前 1.4.0 Installation 不变。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_coordinator.py` | 原路径 | prepare→IPC→snapshot verify→commit 编排；数据库 adapter 仍 PENDING | 29c1f322a12dd48a72438e0d6d475220be97773aad9f1b23d593f7208d3eb9a4 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_coordinator.py` | 原路径 | 顺序、hash、篡改和三阶段异常零重试合同 | 487b7ef5be65c6c89ee0ab45c95206af35b8e416bb8ab77a6eaab6b5cc45cc8d |

### 9.20 阶段评审数据库双事务适配

2026-09-12：新增 `StageReviewDatabasePhases`，将 prepare 与 commit 固定为两笔独立短事务；第一笔事务
固定 command hash、非空 authority snapshot 与 exchanges，事务关闭后 coordinator 才调用已安装 Growth
包。全部 IPC exact 成功后，第二笔事务重读 current snapshot，只有 canonical JSON exact 相等才调用
publisher，且 publisher 返回检查发生在事务提交前。

IPC 期间活跃事务为零；IPC 拒绝/超时/取消不打开第二笔事务，current 漂移零发布，publisher 异常回滚，
各阶段均零重试。数据库回调限定同步且事务体无 await，避免取消后后台线程继续发布。真实 Owner snapshot
builder、StageDecision publisher 与命令入口接线仍 PENDING；当前 1.4.0 Installation 和真实租户数据未变。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_coordinator.py` | 原路径 | prepared 增加非空 authority snapshot 完整性封印 | c471c6c180fc1273445e149cbc283c464b9c6799363f423078a2fb91e2fc0cfe |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_database_phases.py` | 原路径 | 双事务 prepare/current-revalidate/publish adapter；具体 Store 接线仍 PENDING | af318535aaa438181f4e1f3558658f06853d2d2137501eddf172955a9a8d11f7 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_coordinator.py` | 原路径 | authority snapshot 空值与篡改拒绝回归 | 2c66a60998e45659a632688bf77984c410e2834f8e861340e05142c321e65c29 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_database_phases.py` | 原路径 | 无跨 IPC 事务、漂移零发布、异常回滚与零重试合同 | 190a624aaabbacf666de686980dfc7126ebb1dcfa8f33aa8024b2a9a10f32e7b |

### 9.21 阶段评审 StageDecision Owner 双事务绑定

2026-09-12：新增 `StageReviewDecisionOwnerBinding`。prepare/current 两笔事务对同一 decision target
与 idempotency key 取得排序 advisory lock，读取真实 StageDecision head 和 authority Receipt，并将四种
package validation exchange 的 canonical hash 与 trusted authority snapshot 一起封印。四种结果齐全且
第二事务 snapshot exact 相等后，publisher 只调用既有 `AnalystStageDecisionStore.put`。

旧同步 command 的 identity 条件抽成宿主 helper 并原位复用。异步新发布路径发现同 key Receipt 时在
authority reader 前拒绝，保留给后续 Owner replay fast path，禁止为历史重放重新读取失效来源或调用
四门 IPC。真实 Task/Plan/Run、职责、runtime、Eval 复合 reader 和产品异步入口仍 PENDING；当前
1.4.0 Installation 与真实租户数据未变。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py` | 原路径 | 提取并复用宿主命令 identity helper；旧同步行为不变 | b2477ad290264f084f8e36b1d7f121563c499d99a2f21b460553c7d0227452b6 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_owner_binding.py` | 原路径 | 真实 Owner head/Receipt snapshot、四门完整性与唯一 Store publisher | e573beaeea089b9ce6360e7792fed8fa625ae5c28b55b6a13ddaffe1d1c34b9b |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_command.py` | 原路径 | helper scope 与严格整型版本回归 | 772e8919e42c467d87fc71bc0683504f2173426ff2de010f6e21276b3728b8ff |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_owner_binding.py` | 原路径 | 隔离 PG 发布/回读、竞争漂移、replay fast-path 和四门完整性 | 5787623c9d8d3bd806b6701785f9ea48d322e52e1be55f1b554a290d8f7ff864 |

### 9.22 阶段评审结构化 Eval 输入 hash 第五门

2026-09-12：审计发现旧 `_sources_and_eval` 仍在数据库事务内调用包侧结构派生，不能直接接入
9.20 双事务。作者包 review operation 因此新增严格 `validate_structure_case` 消息：输入原 query、stage
和 Owner 读取的 expected Eval case input hash，复用包内 parser/validator 派生后只返回 exact hash，
不返回 query、Evidence 内容或 case。宿主 port、prepared 上限和 Owner 完整集合同步为五门。

错误 hash/消息/query 均 fail closed；旧 1.4.0 不含新消息并继续拒绝，未修改 Installation、Registry、
runtime binding 或租户数据。真实复合 authority reader 与未来 1.5.0 Candidate 仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py` | 未来 1.5.0 Candidate | review dispatcher 接受第五种严格消息；当前安装不变 | aafb1c7938c8a920666194ea353918d1965399bce89fcff5170f2f4cb165cb4c |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analyst_stage_review_runtime_operation.py` | 未来 1.5.0 Candidate | 结构 case 派生与 Eval input hash exact 校验 | 216105dc5035f3ea7e048d131a403390e977f2ba6afe540df98054fe9e4eeed7 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_package_port.py` | 原路径 | fifth kind one-shot transport | 76a8886b1ac8cfe7e12a0b955b77956fdc004efbaab61f4b1da532c2c4220b59 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_coordinator.py` | 原路径 | prepared 上限五条；六条拒绝 | 3b381dafdf22d61893d1fdce5ff3fb51873c1cfeaf44478615e217a6ae5710f4 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_owner_binding.py` | 原路径 | 新发布必须五门齐全 | 179b6dba153cdfd3ffd0b4da06cd4c226e8ebdf9fe8d19a20c1c7dcc7c3805e4 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_runtime_operation.py` | 原路径 | 三阶段真实 prompt 与错误 hash | 616304d28f3ff4a7353405a327e3caff967251d5032606e10b9f378d259554d9 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_installed_port.py` | 原路径 | fifth kind transport 回归 | 4a0a91a2264415e02fcb9bdaaa7b6b443d4235a64eb83f2d8cdb3c430657613e |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_coordinator.py` | 原路径 | 五条允许、六条拒绝 | 96df3afba850c733fdd4f77af76e6a9b33a43dd5aebc668d2be7f7fe8ef02e09 |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_owner_binding.py` | 原路径 | 五门 Owner 发布完整性回归 | 5e2a61bdac796779c1e6eb2a94d3475969dd7bccfd4864fa95572586863bb68b |

### 9.23 阶段评审 runtime proof reader

2026-09-12：`read_stage_review_runtime_authority` 复用现有 Task/Plan/Run、最新 StepRun、Checkpoint
及 Observation Evidence 的真实只读校验，在同一事务输出可 canonical 封印的 runtime snapshot 与
`validate_runtime` payload/expected。payload 中 observation 来自数据库 actual Evidence；snapshot
固定 task/run 状态、plan/attempt、checkpoint state/dependency hash 和 Evidence id/content hash。

原 `require_stage_review_runtime` 保持签名与 plan 返回值。reader 不 IPC、不写库、不读取调用方提供的
observation；职责与 Eval/source proof reader 仍 PENDING，单个 runtime proof 不构成发布授权。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_runtime.py` | 原路径 | 真实 runtime snapshot + validate_runtime message；兼容 wrapper 保留 | 3343ef47c153251837124874a76ae53bcb49a82130cbbd5c282b6a04507c8b9a |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_runtime.py` | 原路径 | 三阶段真实 PG proof、canonical JSON 与旧拒绝合同 | bcbf4dbe5d22e25a3d84ef20f3b618eeb5bc63882dd90f8783ae4d64259a043c |

### 9.24 阶段评审 responsibility proof reader

2026-09-12：`read_stage_review_responsibility_authority` 复用当前 ResponsibilityPlan、唯一人工阶段槽、
租户 membership、AssigneeResolution Receipt 有效期/body hash 与 Owner exact resolution 校验，在同一事务
输出可 canonical 封印的 responsibility snapshot 和 `validate_review_slot` payload/expected。

原 `require_stage_review_authority` 保持签名与 reviewer 返回值。reader 不 IPC、不写库、不接受调用方
slot/Receipt 内容；Eval/source proof reader 与五门组合仍 PENDING，单个职责 proof 不构成发布授权。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_authority.py` | 原路径 | 真实职责 snapshot + validate_review_slot message；兼容 wrapper 保留 | 08a88647c32b92e9e967aded1492fcfc7c67b833c0de970af2e4c028ba519ee5 |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py` | 原路径 | 真实 PG proof、canonical JSON 与旧拒绝合同 | 18d574c313f52640e3f3dfa8b0567bcb0946e0b7585434713f4c008c18b3839f |

### 9.25 阶段评审 Eval/source proof reader

2026-09-12：`read_stage_review_eval_source_authority` 复用原 subject/source/Eval 全链只读核验，但不在
事务内调用 Growth 包；它输出 `validate_eval_proof` 与 `validate_structure_case` 两条 exact 消息。
structure expected hash 只来自当前 Suite 唯一 required positive case，Eval proof 绑定当前 tenant、
artifact、attempt、contract、policy、cutoff、report 与事务时钟。旧同步命令仍显式调用 deriver 一次并
比较同一 case hash。

host reader 两条消息已由作者包 operation exact 接受。尚未组合五门、接产品异步入口或改变 1.4.0。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py` | 原路径 | Eval/source proof 模式与旧同步兼容包装 | 82d7507e3595dc0ac876583b553a5f5bb8a5e00c37eb76acb5fc9a1a1e76f6ee |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_command.py` | 原路径 | 零 deriver proof、canonical JSON、真实 query 包 parity 与旧漂移回归 | 325c748c7d184a79d0dd93bf7995b6a10321a13cf127a8b44d9fdf8d797d5b5b |

### 9.26 阶段评审五门 composite authority reader

2026-09-12：新增 `StageReviewCompositeAuthorityReader`，只组合宿主 command identity 与 9.23～9.25
三个真实 proof readers，固定生成 command、slot、runtime、Eval、structure 五个 exchange。单一 snapshot
封印 command payload hash 与三个组件 snapshot，不复制原 query；markings 在构造时固定，命令不能覆盖。

Owner binding 向 reader 传递真实 key/expectedVersion。组件 shape 漂移在 IPC 前拒绝。内部异步 service、
Receipt replay fast path 和 1.5.0 安装仍 PENDING；当前无产品入口、无运行或租户数据变更。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_composite_authority.py` | 原路径 | 五门固定组合与单一 authority snapshot | 9aaa2a81022e0012927dead1fcfeeb5cd538b8d4119b2352a3672cc40ae3c903 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_owner_binding.py` | 原路径 | reader 获得真实 key/expectedVersion | d64be783285bc142c31b74bc6ba4651cc9b13eb9b401b1724ec3172ce46ffa98 |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_composite_authority.py` | 原路径 | 顺序、shape、markings 与 canonical snapshot | b387739cdd98e98b6f45ab4c2c85f4680312db6e4294829523441fc5da3c5af7 |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_owner_binding.py` | 原路径 | reader 签名与真实 PG 五门回归 | 69fa86a1cda5fa6ade8505ccb6d8a4c4ee0c3fe6e1baaa34ebd8d62c914bc74a |

### 9.27 阶段评审内部异步 service 与 replay fast path

2026-09-12：新增 `AsyncAnalystStageReviewCommandService`，内部装配 composite reader、StageDecision
Owner binding、双事务 phases、installed one-shot port 和 coordinator。decide 先用独立短事务读取同 key
Receipt；命中后 Owner exact 回读并比较完整 item/version，零 proof reader、零 IPC 返回历史 ref。

新发布按 prepare→五次事务外 IPC→current/publish 执行；超时未知零写。service 尚无公开入口，真实
installed invocation factory 与 1.5.0 安装仍 PENDING，当前 1.4.0 和租户数据未变。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_async_service.py` | 原路径 | 内部 async 装配与 replay preflight | 918354d7f1415a046cee7a419a101910ad1a8a3ff67e6c399b279e0847f18262 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_owner_binding.py` | 原路径 | exact Receipt replay Owner 回读 | 4422194578103acf404892eb83ecdb8805b530fb5cb91e9e05a8064451d32142 |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_async_service.py` | 原路径 | 新发布/replay/conflict/timeout 隔离 PG | 1f1f95b4957f498da8c827087a2b4678ffd8117aef60cef42e61ea4de80da5b7 |

### 9.28 已安装运行时 live owner 一次调用窄缝

2026-09-12：审计确认签名 OCI session 的唯一所有者是 `PreparationOwner`；重新打开相同 resource
或把 session 交给业务 service 都会破坏资源租约和单一 owner。现有 owner/PreparedJob 因此只增加
一次调用窄缝：按 `PreparationPlan.members` 中 package id/content hash 唯一选择 owner 内 session，
同 owner 串行调用，停止时取消并收敛在途调用，session 对象始终不逃逸。

错误、超时、取消均零重试；declared operation 仍由 `RuntimeSession` 校验，所以旧 1.4.0 缺少第五门时
明确拒绝。本切片没有 live-job directory，也没有 Installation/generation/binding epoch 前后当前性复核，
因此尚不构成 installed invocation factory，未接 stage-review service，未修改租户数据或安装状态。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/preparation_owner.py` | 原路径 | owner 内一次调用、串行和清理收敛；session 不逃逸 | bade722713d0fee9e4777283e4493c5f5b6019103b2e147cdcd292367cc41374 |
| `services/aos-api/aos_api/extension_runtime/preparation_worker.py` | 原路径 | 按 plan member exact package id/hash 选择 live session | 48ebb2ebccc8c2705ef378273dbc22dcba13e08069e85dbbfa46df6ff8cd715b |
| `services/aos-api/tests/extension_runtime/test_live_owner_invocation.py` | 原路径 | 原位调用、串行、零重试、package 绑定与 stop 收敛合同 | bd75d693432349599d8e32ea5dea07821382bc8a8d7cdd799462c6e719db96a2 |

### 9.29 Live PreparedJob exact 目录

2026-09-12：新增进程所有的 `LivePreparedJobDirectory`，目录键只从真实 `PreparedJob` 派生为
TenantScope/Installation/generation。相同 owner 重复登记幂等，同键竞争 owner、跨租户、错安装和错代际
均拒绝；撤销必须匹配原 job 对象。

`PreparationConsumer` 在 owner routing 校验成功后登记，在关闭时即使 stop 异常也撤销；登记冲突先
停止新 owner。目录不读取或缓存授权，不持久化 token，不启动运行时，也不构成当前 Installation、
binding epoch 或 package lock 的调用许可。当前性前后复核与 stage-review service 装配仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/live_job_directory.py` | 原路径 | exact live job identity directory；无 admission 权限 | 9c211d1228587d297572b3de7b37500ac24e1b0ffde3d59d6bc05654df42207e |
| `services/aos-api/aos_api/extension_runtime/preparation_consumer.py` | 原路径 | owner 校验后登记、关闭必撤销、冲突先清理 | fc4d1e0deacd13dd2252c66c005eba9686b39f0c681592f0f61346d300278de1 |
| `services/aos-api/tests/extension_runtime/test_live_job_directory.py` | 原路径 | exact lookup、竞争/隔离拒绝与 consumer 生命周期合同 | b1fba96a76b6ee6155bdcdda8272ce7ba7e097af728cabdc988d7a426d666396 |

### 9.30 当前已安装 package 前后快照调用门禁

2026-09-12：新增 `CurrentInstalledPackageInvoker`。第一笔短事务锁读 active Installation ref 和指定
generation binding，复用 canonical baseline reader 校验 lock，要求 ready/enabled/unfenced、exact
installation revision/lock hash，并检查调用 markings 覆盖 lock target markings、目标 package 唯一。

事务关闭后才从 9.29 live directory 解析 exact job 并调用一次；IPC 返回后第二笔短事务重读完整
Installation/binding/package/markings snapshot，任何漂移都丢弃响应。异常、超时、取消不重试，不在
事务中 await，不缓存 admission token。stage-review composition 与最终 commit runtime snapshot 封印仍
PENDING，本切片无数据库写入或真实租户状态变化。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/installed_package_invoker.py` | 原路径 | active Installation/binding/lock/marking 双快照包围一次 live IPC | d868b18c1c4f4c726b1986f377172fb8f74bac30de487122858aecc8c3d740c4 |
| `services/aos-api/tests/extension_runtime/test_installed_package_invoker.py` | 原路径 | 事务外 IPC、漂移丢弃、隔离/marking/package 与零重试合同 | 47df876705c6eb55732b86e8b6b218bed6555671973ab2682ecbdc7b6db03d60 |

### 9.31 阶段评审与当前已安装运行时组合封印

2026-09-12：`CurrentInstalledPackageInvoker` 的 snapshot reader 收窄为只接受 `HostTransaction`。
`AsyncAnalystStageReviewCommandService` 新发布在原业务 authority snapshot 中加入 `installedRuntime`：
prepare 事务封印一次，五门 IPC 完成后的 commit 事务再读一次，exact 相等后才允许 StageDecision Owner
发布。第五门成功后发生 binding/epoch/lock/package 漂移也会零发布。

新增正式 `build_current_installed_analyst_stage_review_service`，调用方法和 snapshot reader 必须来自同一
concrete invoker。历史 Receipt replay 不重新要求当前 runtime 存活，继续零 proof、零 runtime read、零
IPC。当前无公开入口，production control plane 尚未持有 live directory，1.5.0 candidate 也未安装；因此
真实租户 stage-review 仍未激活。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/installed_package_invoker.py` | 原路径 | HostTransaction-only snapshot reader 与一次 IPC 前后当前性 | 6f14f6ad0e00f5a91850baee6de03f608c4678f75c046d84a772866bfdd12242 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_async_service.py` | 原路径 | installedRuntime prepare/commit 封印与 concrete factory | 5ffda95e508ede17a95503d86e31ecbe6fd58685144931272587f924cc3cc3ec |
| `services/aos-api/tests/extension_runtime/test_installed_package_invoker.py` | 原路径 | 同一 invoker factory 与既有当前性回归 | 7403b9105bf8ccbb2b0b8e4da6de38c90803cd225ed03d5abd98ff4f4296f463 |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_async_service.py` | 原路径 | 第五门后 runtime 漂移零发布与 replay 零读取 | 54df3880d36cba2a0b92888c1229c9accd245c33b4cce1f5456b71e9eea3ad6f |

### 9.32 Production control plane 唯一 live directory 所有权

2026-09-12：`RuntimeControlPlane` 新增进程所有的 `LivePreparedJobDirectory`，正式 builder 每次恰好
创建一个独立空目录。app lifespan 持有同一 control plane 对象，退出时清除；构造阶段不连接数据库、
不启动 OCI、不登记 job。

目录存在不代表 runtime host active、Installation ready 或 package 可调用。production host 当前仍只
装配 recovery/configure/disable，runtime-apply/verify/enable 的 live owner orchestration 仍 PENDING；
因此当前目录会保持空，stage-review factory 仍 fail closed。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/asset_registry/control_wiring.py` | 原路径 | control plane 持有唯一 live directory；纯 wiring | ece42c19d637ca264f0e6bacc265169ef1ae280fd65ce4df09ac3930c7c4b5e2 |
| `services/aos-api/tests/extension_runtime/test_production_runtime.py` | 原路径 | builder 独立目录与既有 selector 零访问回归 | cfb83f4beb2f48d93a135239705f7c5a4b7b7534eecf69c86cf81e95bf004d71 |
| `services/aos-api/tests/extension_runtime/test_runtime_startup_composition.py` | 原路径 | app lifespan exact directory 持有与清除 | 5db65270ec08e28e6494113ab52e4d4ea66c1a60a08e604db67acd4063c4f6ee |

### 9.33 单 Installation live lifecycle owner

2026-09-12：新增 `LiveInstallationLifecycleOwner`，只接收 exact `PreparationConsumer`，在一个进程
owner 内固定消费 runtime-apply、runtime-verify、enable。后两段只通过 preparation 保留的同一个
`PreparedJob`、同一 trusted connection 和 TenantScope 执行；不重新打开签名 session。

无 live job 时不进入控制阶段；verify 返回失败或抛错时不进入 enable。tick 串行且由 owner 持有，调用
方取消不取消后台动作；停止先等待 tick 收敛，再复用 preparation stop 的 OCI 清理和 directory 撤销。
本切片尚无可信 Installation 发现、owner factory 或 production wiring，真实租户 runtime 不会自动启动。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/live_installation_owner.py` | 原路径 | 单安装三段有序 delivery、失败短路与 owner 停止收敛 | 6e4e90a9db5d5a3cc01546789e321337318dbe802b601fd05b000fe1235b8de1 |
| `services/aos-api/tests/extension_runtime/test_live_installation_owner.py` | 原路径 | 顺序、同 owner、失败、取消、并发与停止合同 | df6c9d81b648cfaee679c0b1feb020fc7e37cf645e5af1366eab108af28ec07f |

### 9.34 Pending preparation 目录与 exact owner factory

2026-09-12：新增 tenant-scoped pending preparation 目录，只在 `aos_runtime` 独立事务中读取当前租户
immutable event/outbox/operation，固定筛选未投递 runtime-apply。结果按 Installation UUID 排序、去重并
限制 100；不 claim、不 ACK、不读取 active binding，也不把 outbox 路由事实变成执行授权。

新增 exact owner factory，只组合宿主已经完整构造的 `PreparationWorker`、control-plane 唯一 live job
directory、connector、scope 和 descriptor，返回未启动的单 Installation owner。active binding 不进入
创建目录，防止重启后冒领丢失的签名 session。scheduler、正式 worker composition 和 production wiring
仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/pending_preparation_directory.py` | 原路径 | 有界 pending apply 路由读取与 exact owner factory | e9f3e2cc8c45eaea9f7a2be1beed00dfb6a13c8972a582992d495c1b0c2a22dc |
| `services/aos-api/tests/extension_runtime/test_pending_preparation_directory.py` | 原路径 | 类型、排序、上限、跨租户与零启动 factory 合同 | 07ef9030b13c5fd021769610dbb2865b0ce8507ce048987165031b03d4693fb4 |
| `services/aos-api/tests/extension_runtime/test_pending_preparation_directory_pg.py` | 原路径 | runtime role、租户、delivery/kind 与脏连接真实 PG 反证 | 8a313398323853500e622719d3962d092f75de2cbe03714bfec22e2fc5f9390c |

### 9.35 Tenant-scoped live Installation scheduler

2026-09-12：新增有界 `LiveInstallationScheduler`。它只从 9.34 pending-apply descriptor 创建新 owner，
同 Installation 本进程只创建一次；此后即使 apply event 已 ACK、descriptor 消失，仍继续按 UUID 顺序
tick cache owner，以承接 verify/enable 和已安装 package 调用。

caller cancellation 不取消 owner 持有的 tick；identity revoke 等待 tick 后只停止 exact owner。host stop
先等待在途 tick，再隔离 cache 并逐个 stop；单个 cleanup 失败不跳过其余 owner。scheduler 尚未接入
production assignment，disable 前撤销和 assignment replacement cleanup 仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/live_installation_scheduler.py` | 原路径 | 有界创建/保留、串行 tick、identity revoke 和全量 stop | 06d49439db13698376167a50a5b430ca91e04938be05274b23256b3a49e621c2 |
| `services/aos-api/tests/extension_runtime/test_live_installation_scheduler.py` | 原路径 | 保留、排序、上限、失败、取消、撤销与清理合同 | db1d616847a127818f3c53cbc9224c5da3df8bec4becd17cd138ae74b7b87380 |

### 9.36 Runtime host live lifecycle 与 disable exact handoff

2026-09-12：typed tenant assignment 可选持有 same-scope live scheduler。host 固定在 recovery/attempt
recovery 后运行 lifecycle，再执行 configure 和 disable；assignment identity 替换/删除与 host stop 都会
收敛旧 scheduler，即使 tick 失败或 assignment 没有同步 consumer 也不漏清理。

disable consumer 的兼容 `run_once` 被等价拆为 exact claim/finish。带 lifecycle 时 host 先 claim 同一条
lease、读取其 Installation identity、撤销 exact live owner，再执行原 disable executor 与 ACK/retry。
撤销失败零 finish、零 execute、零 ACK。production selector 尚未创建 scheduler，正式 worker composition
仍 PENDING。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/disable_consumer.py` | 原路径 | exact disable claim/Installation/finish，旧 run_once 兼容 | aa1de99e64eda1146238e40887b5267ecb07cd081287dcae0df739d4053f8f0f |
| `services/aos-api/aos_api/extension_runtime/live_installation_scheduler.py` | 原路径 | exact owner identity lookup | 03053a24234a6acfd2ae977e868ea09ce390e469a69a1927328ba39453c09dba |
| `services/aos-api/aos_api/extension_runtime/runtime_host.py` | 原路径 | recovery-first lifecycle、disable handoff 与 assignment cleanup | adf78ac37f25c2ed7502e250ab8937e8479008bbf5f7168bae67f4f054a43fd4 |
| `services/aos-api/tests/extension_runtime/test_runtime_host.py` | 原路径 | 顺序、replacement、stop 与 revoke-failure 零 finish 合同 | 3a96d0c96b19e438cef3f0d18a0c71fae4d2fa32c4dc7d842ad376c1db3f5ddc |

### 9.37 Current published runtime release/artifact reader

2026-09-12：新增正式 runtime release artifact reader。record 在 exact TenantScope/runtime role 的独立事务
读取唯一 published coordinate/content hash，canonical 转换后再次校验 identity。artifact metadata 必须
relativePath 唯一且所有持久 artifactRef 归一到同一个 `bundle://` source；bytes 由 exact allowlisted
ManifestLoader 读取，并再次比较持久 size/digest。

reader 不缓存 record/source/bytes，非法 path/limit 在查库前拒绝。production worker composition 尚未注入
该 reader，本切片未启动 OCI 或改变安装状态。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/runtime_release_artifacts.py` | 原路径 | exact published record、唯一 source、allowlisted artifact 双校验 | 1bd2992cd27b780f794cc8a696c437fdbfbc9b312d1716e1c3dbf0346babdda8 |
| `services/aos-api/tests/extension_runtime/test_runtime_release_artifacts.py` | 原路径 | source/path/size/digest/identity/row cardinality 反证 | a84007de35312bfe0076e7f8b23932a36ba605c69f553ef002f75e1642d77718 |

### 9.38 Production PreparationWorker 可信依赖闭包

2026-09-12：新增 exact `ProductionPreparationDependencies`，固定同步 runtime connector、PostgreSQL
Installation store、同一 policy/revalidator、同 trust-root loader、apply/verify/enable 当前权限、同 store 四来源
配置授权、完整 OCI driver、显式 Linux platform 与 control-plane 唯一 live directory。任何 concrete 类型、
operation 或依赖图 identity 混搭均在构造时拒绝。

per-tenant builder 用同一个 `CurrentRuntimeReleaseArtifacts` 同时提供 record、member artifact 与 schema
conditions 读取，组合未启动的 PreparationWorker、pending directory、owner factory 和 scheduler。legacy
无 selected-release artifact reader 固定拒绝。构造零数据库、零制品、零 OCI 调用；production selector 尚未
接入该闭包，因此本切片不启动 runtime、不消费 outbox、不改变 1.4.0 或租户数据。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/extension_runtime/production_preparation.py` | 原路径 | exact production worker dependency graph 与 per-tenant scheduler builder | fa4fe195a9244a941cc5794a3d7c2db26dac974e5d10c59aaad33cf8c055cda9 |
| `services/aos-api/tests/extension_runtime/test_production_preparation.py` | 原路径 | 同源权威、权限/platform、租户隔离与零副作用构造反证 | fc6a01a40a5e671bee0b04f60a3d1bf95b6b46fd2d3c290be4dff70d32fc40b8 |

### 9.39 Production host preparation lifecycle 接线

2026-09-12：正式 host wiring 新增显式 `AOS_EXTENSION_RUNTIME_PLATFORM` 门并组合 9.38 preparation
闭包。缺任一环境配置或 platform 非 linux/arm64、linux/amd64 时保持 inactive。selector 要求 preparation
connector 就是完成身份验证的 runtime connector；worker dependency graph 还要求 preparation 与
configure/disable 共用 Installation store、四来源授权和 OCI context。

assignment 仍只在 directory/runtime/web 三平面 identity preflight 全部通过后 materialize；每个 exact
TenantScope 现在持有 same-scope scheduler，并继续由 assignment revision cache 与 host replacement/stop
逻辑收敛。本波没有主动启动 host；真实 PG 无 pending apply 回归只执行有界只读发现，零 OCI、零 ACK、
零租户状态变化。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/asset_registry/control_wiring.py` | 原路径 | server-owned policy/loader/driver/platform/preparation 完整环境装配 | d7e705a153f66455bd70c82f518aa99249edf8bb2fd47d06e3c03f509fdf370e |
| `services/aos-api/aos_api/extension_runtime/production_runtime.py` | 原路径 | 预检后 same-scope lifecycle assignment 与 connector/依赖图一致性 | 1feb37282c65c775de36f1473adf84a686d17a788507cef4e62dd83e44f98689 |
| `services/aos-api/tests/extension_runtime/test_production_runtime.py` | 原路径 | 配置/platform/connector/预检/cache/lifecycle 反证 | 2434293e49d62a250a72da2f281e7acef2591e52fe3fbb82b0bb96bf167b0b5a |
| `services/aos-api/tests/extension_runtime/test_runtime_host_directory_pg.py` | 原路径 | 三平面真实 PG 与 same-scope 无 pending lifecycle 回归 | c19888c6b46180db10296adabb5380fc4cb701d9bf2a5618d86bc8a3a122dc6b |

### 9.40 API lifespan concrete live scheduler 启停证据

2026-09-12：新增 app lifespan 组合合同，使用 concrete RuntimeHost、exact TenantScope assignment 和
LiveInstallationScheduler。线程事件证明 ACTIVE 后台宿主至少完成一次空 pending 读取；factory 零调用、
owners 始终为空。退出后同一 host/scheduler closing，后台任务、stop events 和 app state 全部清除。

本切片未修改生产代码。空 pending 反证保证零 OCI、零 claim/ACK、零租户状态变化；它只补齐 9.39 正式
接线进入既有 lifespan 后的启停闭环，不构成 1.5.0 发布或安装证明。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/tests/extension_runtime/test_runtime_startup_composition.py` | 原路径 | concrete host/scheduler 首 tick、唯一任务与 graceful stop | c14621a3c5e30b9b1d263c4c28a15c85cb57ffec1a8039b98ca4dac61b188c88 |

### 9.41 Ecommerce growth 1.5.0 candidate 不可变升级审计

2026-09-12：确认 1.4.0 是 73 文件、tree hash `4dc6cf...` 的历史快照，backend 为 20 文件、
hash `959f15...`；当前作者 backend 已增至 34 文件、hash `0d9a0b...`，包含 14 个新增经营参谋/阶段评审
模块和 3 个修改文件。现有 runnable test 将历史 1.4.0 与最新作者树比较，实测仅该项失败，其余 4 项通过。

下一 candidate 固定为 1.5.0：克隆 1.4.0 的完整已版本化内容，整体替换 current author backend，只提升
manifest version/displayName；1.4.0 改以完整树/backend hash 固化，禁止覆盖。OCI build、签名、publish、
Installation upgrade 仍分波执行，本切片零租户、Registry、OCI 和 Provider 副作用。

### 9.42 Ecommerce growth 1.5.0 unsigned source candidate

2026-09-12：新增 fail-closed 生成器与 87 文件 1.5.0 source candidate。生成前 exact 校验 1.4.0 完整/
backend hash 和 current author backend hash；目标存在、输入漂移、自引用数量漂移均拒绝并清理半成品。
候选继承 1.4.0 完整内容，整体替换 34 文件 backend，提升 manifest 与八个内部 bundleRef。

1.5.0 tree hash 为 `34cd4b...`，backend hash 为 `0d9a0b...`；1.4.0 完整/backend hash 独立固化且
零修改。builder preflight 已指向 1.5.0 并保持 4 bundles、3 runtime members、8 modules、12 operations。
本切片仍 unsigned，无 OCI build、签名、Registry publish、Installation upgrade、租户或 Provider 副作用。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `bundles/candidates/ecommerce/solution.ecommerce.growth/1.5.0/` | 原路径 | 87 文件 immutable unsigned candidate tree | 34cd4bc2e9f6bc9c2d9ceb0cf8bee16a93232bce374396e075c3afae9c5b43d8 |
| `scripts/prepare_ecommerce_growth_1_5_candidate.py` | 原路径 | exact base/author hash、版本自引用与半成品清理 | 72496830e24b7a2bf1da4db3d2b9f608abac1b91b605fb181abc13782a95f9a3 |
| `scripts/build_ecommerce_runtime_candidates.py` | 原路径 | current growth build coordinate 提升到 1.5.0 | 31fe759651303a9109260964313456aa2fc2d5e676258a6633ff9edcd6487063 |
| `services/aos-api/tests/extension_runtime/test_runnable_ecommerce_candidates.py` | 原路径 | 1.4.0 历史 hash 与 1.5.0 current exact 合同 | 0e2622ffa2532cf7d5978b6b8ca8e618316a7d1a4b3b1c82ac533278e79749b7 |
| `services/aos-api/tests/extension_runtime/test_prepare_ecommerce_growth_1_5_candidate.py` | 原路径 | deterministic generate、漂移/覆盖拒绝与自引用反证 | 83091b57001d16a0b601aa0669d85d2e0504c53740603ea373bd8541c375e2d2 |

### 9.43 Ecommerce growth 1.5.0 isolated OCI qualification

2026-09-12：在具备 userns/seccomp 的 `colima-aos-extension` 唯一执行 build，仓外输出 tree hash
`ea4dab...`，growth content/config/image 分别为 `416bfd...`、`20feb6...`、`7850aa...`。随后读取 exact
build Receipt 完成 ephemeral qualification，snapshot hash `3cd775...`，resolved growth 为 1.5.0。

3 runtime admissions、3 schema requirements、8 modules 与七类 tamper rejection 通过，ephemeral signature
未持久化；两阶段四类业务 effect 全为 0。18436 与临时 Registry 容器已清除。本切片没有持久 Registry
publish 或 Installation upgrade。

### 9.44 Ecommerce growth 1.5.0 Registry successor 与持久运行根

2026-09-12：首次 v1 apply 在 create_version 前因 1.5 displayName 改变、违反 Registry bundle 跨版本 identity
而拒绝；Registry 1.5 仍为零。修正 Candidate 继承 1.4 稳定 displayName，不放宽 Registry，1.5 source tree
由 `34cd4b...` 更新为 `34446f...`，backend `0d9a0b...` 与 1.4 immutable hash 均不变。v2 OCI build /
qualification 各一次成功，output `ebadbd...`、growth content `6a5471...`、snapshot `b6e747...`。

生产 allowlist 在明确配置 server root 时同时兼容历史 persisted `a0v-canonical` alias；未配置时继续 fail
closed。successor 复用持久 key/trust root，生成含 growth 1.4 与 1.5 的五坐标 signed tree。Registry 首次
mutation 为 create/validate/publish 各 1，重放三项均 0；1.5 唯一 published。`.env` 持久化 bundle root、
trust-root path 与 linux/arm64，每项唯一非空且被 gitignore。Installation 前后仍为正租户 1、负租户 0，
当前正租户仍 approved growth 1.4；本节没有 OCI runtime 启动、Provider 或外部发布。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/aos_api/asset_registry/control_wiring.py` | 原路径 | server root 同源兼容历史 canonical alias | eca81907a686c518655d55f73bc95dd8e91292a61955d7fff24ea2a18fb7e9fe |
| `scripts/prepare_ecommerce_growth_1_5_candidate.py` | 原路径 | 继承稳定 Registry bundle identity | c3a5ebe7d573e35cf7291f72af5d508e01bfd04b082c376e7f318a8826b29322 |
| `bundles/candidates/ecommerce/solution.ecommerce.growth/1.5.0/` | 原路径 | identity-corrected 87 文件 source tree | 34446fcbfc1a8b7239cc44cdb4d801584d618deffbadc9c6bddaf7d69e5b0bd0 |
| `scripts/a0v_ecommerce_growth_1_5_registry_successor.py` | 原路径 | bound Receipt、持久签名、Registry 状态机、配置与安全重放 | 1be94be3e3750ef8f4535089c4f69852600a58ddb11e207b62fd35662a8ee516 |
| `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_growth_1_5_registry_successor.py` | 原路径 | preflight、v4 保留、签名/config 幂等与异常 Receipt | 2fe70bbaafc3502bcef10a6e0991e6b8d0dc3932c4d9a30f775436e3f3444d95 |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/ecommerce-growth-1.5.0-identity-oci-build-v2-result.json` | 原路径 | v2 BUILD_GREEN Receipt | d87d457ce379524bfa4b0368d140b0183c10ac9f8c44fa5669239d52aa05999c |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/ecommerce-growth-1.5.0-identity-oci-qualification-v2-result.json` | 原路径 | v2 QUALIFICATION_GREEN Receipt | 8f0566b0355a1f5e14b6878f459993850cc99fd88b8a2c47353b0f01221a789f |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/ecommerce-growth-1.5.0-registry-successor-apply-v2-result.json` | 原路径 | create/validate/publish 各一与零 Installation mutation | c48554f8d4b90a892984b13dfe3582690616698783adac0011970d6cda5ee2db |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/ecommerce-growth-1.5.0-registry-successor-replay-v2-result.json` | 原路径 | Registry/config/signed tree 零 mutation 重放 | 2f460c65ce38b3b24febd1378d323a3095edf2161f908086a90e3e008fb1a99a |

### 9.45 A0-V 独立 Runtime Host 与 invalid 1.4 fail-closed 证据

2026-09-12：在隔离 `aos_meta_head` 建立 directory/runtime/web 三个互异非特权登录主体，持久凭据仅存
仓外 0600 文件。Host Identity/Assignment 均 revision 1 且重放不增长；正租户 assignment=1、负租户=0。
真实连接探针证明三个主体同库、均非 owner/bypass/superuser，并保持 directory-only、runtime-only、none
成员边界。独立 Host 达到 ACTIVE，18181 诊断 API 继续 host=0。

1.4 首次 preparation 的 v1 过期未 claim Operation 用既有终结命令标记 `PREPARATION_EXPIRED`。v2 通过
当前持久 admin membership 和签名 admission，进入 preparing 后因运行镜像 registration 与签名 Manifest
不一致而 fail closed；终态 `PREPARATION_EXECUTION_FAILED`，三个 resource lease 全部 released/observed，
无 extension container，Installation 仍 approved revision 3、activeRevision null。静态根因是三个后端注册
1/2/9 个 API，但已发布 Manifest 未声明对应 API；禁止放宽 exact registration 或修改已发布字节，改线为
新不可变坐标、完整 Session qualification 与重新首次安装。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `scripts/a0v_ecommerce_runtime_host_bootstrap.py` | 原路径 | 隔离三身份、host identity/assignment、目录函数最小授权与备份 | 0258d15365a1fb7f419adda604201213e73b84b61965fc67067c0f73aaf7943e |
| `scripts/a0v_ecommerce_runtime_host.py` | 原路径 | 单实例独立 Host、ACTIVE/STOPPED/fail-closed 状态 | 633ad20dcc552d4e4a5dcf559174b647b8fef60671f727d6c7bed5596a52feb6 |
| `scripts/a0v_ecommerce_growth_1_4_activate.py` | 原路径 | 当前 membership、过期 apply 收口与受限 apply/verify | 5b34c92a4b1f046a6b8724aee6bab3f30181019a7f0f8ccd1a8b3370289a8a5c |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/ecommerce-runtime-host-growth-1.4-attempt-verification.md` | 原路径 | 三平面与失败清理审计 | ae996920bc7476f7ac096e3aba402c45af70d73669e65f1948d1ef4703ef1019 |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/runtime-host-growth-1.4-attempt/terminal-database-state.json` | 原路径 | Operation/lease/membership/Installation 终态 | 9882e4bcdbc5175900f8f43d0a427545ea026a6ccb5ee89d5cea671d9bcbcd67 |

### 9.46 Invalid growth 1.4 清洁退役

2026-09-12：为从未 active 的 approved Installation 增加唯一受限退役路径。应用 guard、数据库不可变
revision trigger 与完整历史领域模型共同要求：零 Runtime Binding、零未终结 Runtime Operation，且全部
历史 resource lease 已 released/observed；uninstall Evidence 显式哈希真实 `fromState=approved`。active
卸载仍走既有 runtime uninstall Receipt 路径。

隔离库升级前仓外备份 4,571,944 bytes、SHA-256 `322efe8d...`；Alembic 从 a0v_012 升至唯一
head a0v_016。真实 1.4 Installation 从 approved revision 3 退役为 uninstalled revision 4，首写成功、
相同幂等键重放；clean/canary/effect 计数均为零。失败 preparation Receipt 与 released lease 历史保留。

| sourcePath | targetPath | decision | 当前切片SHA256 |
|---|---|---|---|
| `services/aos-api/alembic/versions/a0v_016_clean_approved_installation_retirement.py` | 原路径 | 数据库双重清洁守卫与 forward-only 迁移 | 2ebd533e627f4e3da0d6635223ec1cf360fe2493fff904af41bbcfff5e5cf27a |
| `services/aos-api/aos_api/asset_registry/composition_contracts.py` | 原路径 | 完整历史接受受限 approved 退役 | d637c69ce3dd8f5fdfc96f7ba769acb6a9cdf48818ce0501932c3f1822a0dace |
| `services/aos-api/aos_api/asset_registry/installation_evidence.py` | 原路径 | uninstall Evidence 封存真实 source state | 633ebc0b90d48f8a171dc7c263986492973385d7a70a32331b196220bb2c9a67 |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/invalid-growth-1.4-retirement-verification.md` | 原路径 | 迁移、退役、回放与无副作用审计 | 43bad01ddb8f814e0990c7edb723d6d7d9a3e77a582d03dddd4904534ee64c4c |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/invalid-growth-1.4-retirement/uninstall-result.json` | 原路径 | 真实退役与幂等回放 Receipt | 35f949cc3e07ec98a1f0fee3455e211b66819cc740567c906a9d7ac9ba468485 |

### 9.47 三包完整注册新候选

新增 domain 1.2.0 / Niushop 1.2.0 / growth 1.6.0：完整签名 contribution 与运行注册同步，历史版本字节保留。
候选生成、预检与资格代码验证 22 passed；真实 OCI qualification 尚待执行。
证据：`../A0-V-REAL-AUTHORIZATION-REVALIDATION/ecommerce-1.6-candidate-verification.md`。

### 9.48 三包真实 persistent session 资格通过

2026-09-12：69819df7 的隔离 build 与 qualification 一次通过。domain/platform/growth 完整 registration
数量为 1/2/23，三者 heartbeat alive、cleanup released，七类签名篡改拒绝。Docker 无遗留 aos-ext 容器。
输出树 hash 为 768af3234ae1ff395bcabceceb0a8889e746f689bfae378bf7177a44619be445。
证据为 A0-V 目录 ecommerce-1.6-build-result.json / ecommerce-1.6-qualification-result.json。
下一步按照 ecommerce-1.6-registry-plan.md 进行新三坐标 Registry successor，不修改历史制品。

### 9.49 三坐标 Registry successor

2026-09-12：domain 1.2/platform 1.2/growth 1.6 各 create/validate/publish 一次；重放全部为零。
八坐标签名目录保留历史五坐标的 content hash，宿主根路径 CAS 成功且重放不写。正租户安装仍为 1
（已卸载旧实例），负租户为零。本步新安装/Provider/外部发布均为零；执行器测试 6 passed。
证据：A0-V 目录 ecommerce-1.6-registry-apply.json / ecommerce-1.6-registry-replay.json。

### 9.50 正式首装 applied 与 verify 恢复缺口

2026-09-12：新 Installation 3d267738-ba0a-49ef-812b-d6b72d3374fd 经组合、maker/checker 审批、
独立 Host apply 达到 applied@4，8 工作台/3 依赖边/28 contributions。verify 请求 accepted 后 Host
因 LookupError 退出，三资源已释放，无绑定。真实库 extension_schema_installation 为空；verify 未完成。
本波不能判 active green。下一波入口是 A0-V 目录 ecommerce-1.6-recovery-plan.md，补 Schema 实证与
applied 安装受控恢复；不重写已提交历史、不盲重试原 Operation。首装回归 8 passed。

### 9.51 Schema 实证、恢复首装与持续运行缺口

2026-09-12：三包签名 Schema requirement 与平台迁移/各 13 个物理关系核实完成，首次登记及零写入回放见
ecommerce-1.6-schema-apply/replay.json。a0v_017/a0v_018 补齐 applied→approved 的清洁恢复及审批继承，
首次 reset approved@5，旧 apply 保留、旧 verify 终结；同键回放不重复写。新 apply→applied@6，
verify→active@7（2026-09-12T00:45:54Z），ready/disabled/fenced，canary=0。

资源于 00:48:02Z 到期后退出，00:49:34Z 绑定已 unknown/disabled/fenced。安装时点成功不等于持续健康。
71be0b06 修复空闲宿主不检测资源失效；7bf516cd 增加成功 verify 后 60 秒核验、180 秒短租续约，43 项
测试通过，但尚缺真实 PG/OCI 跨五分钟观测。当前没有运行中的电商 Host，不可将 active 历史当作可经营。

下一波权威入口：A0-V/ecommerce-runtime-continuity-plan.md。优先补已验证但从未启用安装的正式恢复/卸载，
现有 uninstall 要求曾启用后的 disable/detach Receipt，不能伪造该证据。之后真实续租观测、四来源配置、
enable、经营首链与八工作台。全部任务未完成；m1 串行、不 push、230 L0 挂起。自动接续仍 ACTIVE。

### 9.52 正式重装及跨初始期限实证

2026-09-12T01:21:23Z：8707c887 补齐从未启用安装的严格卸载回执；旧安装规范 uninstalled@8，重放不重复写。新安装 efc4e640-1b15-403f-9d06-4c6d1a5330a7 active@5，原期限 01:20:49Z，333 秒观测包含 5 次自动续租、3 个真实 Running 容器、同 generation、ready/disabled/fenced、canary=0。详见 A0-V/ecommerce-reinstall-continuity.json。9.51 无运行 Host 的状态已被此实证取代；当前 Host 持续运行，业务尚未启用。

01:24:43Z 一次真实模型健康调用成功，延迟 576ms，健康有效至 01:39:43Z；新 attempt 独立日志，旧日志保持不变，5 项健康脚本测试通过。下一波继续正式技能发布、数字同事准备、责任计划与配置启用，再验证自然首链及八工作台；不能把运行连续性当作经营闭环完成。
