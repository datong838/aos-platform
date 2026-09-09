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
2. 暂停新 occurrence claim；排空或明确归宿旧在途命令。
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
| `services/aos-api/aos_api/ecommerce_growth_cutover.py` | 原路径 | platform host control port；D5 整组 prepare/commit/rollback 权威，不导入领域 bundle | NEW |
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
