# 任务总控三辅助GET读取审计与接续

Rules：用户/仓库AGENTS、aos-engineering-delivery、231完整Goal与D-wave、单m1新owner、先方案/TaskLease/完整审计再RED/最小编码、保护dirty/当前库READ ONLY/Host worker Provider OFF/unknown不重放。

1/8当前：Authority2016；Operations仅2GET追加972c16c5e已55相邻/代码r2与实际readback r3消费、正常runtime/真实OIDC3GET200，页面169refs/50虚拟库存缺口/0Cases、commands6blocked；650表保持。新维护Task仍active，实际API86349/18080 code972；Web81203 frontend树与972相同；原fullPG/API/Web2324与后API-only972分别证明，不混同。普通customer/operations菜单点击需owned焦点，仅这两个点击已验证。

目标：原任务总控辅助feedBack/dispatch/batch由legacy目录404恢复为真实读取或明确missing roots/unknown，不能通过read建立反馈命令、伪造Receipt、补0成功、启用派发/批量运行。具体待审查GET /views/task-cockpit/feedback、/views/task-cockpit/dispatch-scenario、/views/task-cockpit/batch-scenario。

2/8文件计划（正式Task同名，新owner/base2016且原router Lease已释放）：services/aos-api/aos_api/routers/ecommerce_workshop.py，仅审计证明安全的明确GET才将目录类型换ReadCatalogDependency；services/aos-api/tests/test_ecommerce_workshop_read_http.py维护明确已审计Scope；services/aos-api/tests/test_ecommerce_cockpit_read_dependencies.py新增HTTP专项/原门负向；此证据目录审计/RED/native/actualpage/Prime/Delivery。其他GET/POST/原execute/readiness不可整体替换。

已开始实际内容复习：FeedbackReadModel默认connect_read_only，一个readonly snapshot/querycutoff、bounded ACCEPT feedback commands，再port.read与三个Target.read_receipt、original Artifact/Run、EffectReviewOwner._existing/_verify_review、candidate/memory item SELECT对账。必须完整检查HostTransaction构造/execute、BoundEcommerceGrowthFeedbackPort.read及read_receipt传递helper，不能因read命名或0rows跳过完整审计。actor='ecommerce-cockpit-feedback-read'是原读取标签，不是真人或运行身份，不能拿去签预算/审批。源欠缺或Receipt漂移原503保留，不制造成功反馈。

Dispatch/Batch原factory未指定reader时只组合blocked/no exact roots DTO，不做派发或批量准备。仍须核原factory实际构造、完整read/helper；若日后绑定真实reader，必须重新审计它，不能将当前None reader纯DTO证明泛化为所有未来producer安全。

审计完成后HTTP-specific RED→仅已审核GET注入→原read/场景相邻与租户/unknown/门保留→正常runtime原生readonly与真实OIDC当前API/page→当前冻结独立复审→准确scope Delivery/Authority/Prime→自动下一已登记privateGET或预算有界consumer；源/运行/人工评审/首链/观察/发布不因DTO/页面成立而计完成。

## 传递审计补记
已完整核对默认构造及实际读取分支。纠正连接来源：FeedbackReadModel导入的是通用 aos_api.db.connect_read_only，不是 ecommerce_growth_runtime_connection；前者在首条SQL前开启repeatable-read/read-only并应用租户scope，实际权限仍须验证。构造MemoryCandidateTarget会创建AipMemoryStore，但构造仅保存factory，不连接/写表；read_receipt只经scoped SELECT/纯hash校验，不调用put/worker/claim/ack。Dispatch/Batch当前factory reader=None只返回missing exact roots blocked DTO；不泛化未来reader。静态审计不替代当前正常角色原生读取、HTTP租户/门验证或真实页面。详见transitive-read-audit.json。

原生读取r1：当前972冻结源码、原普通runtime身份、noSUPER/noBYPASS且READ ONLY、原真人admin membership通过。feedback实际0条/hasMore=false，不能视为非空Receipt分支验证或经营反馈已完成；dispatch TASK_GRAPH_EXACT_ROOT_REQUIRED、batch BATCH_EXACT_ROOTS_REQUIRED，全部命令false。诊断仅在此独立进程绑定原runtime DSN，不能代替实际API默认连接证明。下一步三条HTTP RED，保留原503、租户隔离和unknown，再按完整Loop验证交付。

HTTP RED初次9fail/3pass，其中7个是旧目录接线负证据，2个limit断言误写422（项目原错误映射实际400），不计接线RED；已纠正测试匹配原400，不改原错误handler。最小实现只改三个GET参数类型，其他函数体/工厂/所有POST不变。
