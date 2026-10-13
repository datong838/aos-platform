# 下一波：原八台只读read-model安装门调查

Rules：用户初心、231、上位双侧增长产品与恢复方案。八页可点击不是首链；现有404必须调查真实原因，不因预算未续期而把所有读取归因预算。已有签名ACTIVE5八模块明确授ecommerce.workshop.read（原投影没有DATA_SCOPE_NOT_GRANTED）；旧CatalogDependency legacy-only排除所有当前runtime包。

第1/8：复习上位产品与当前authority2011，代码预检已交付98642f8但不授预算/运行。第2/8文件计划：新增ecommerce_workshop_read_catalog.py（仅若审计证明GET可独立于runtime执行，以原签名/安装/真实data-scope为读取条件），routers/ecommerce_workshop.py只允许明确审核的GET注入ReadCatalogDependency；新增test_ecommerce_workshop_read_catalog.py证明无身份/租户/锁/签名/数据scope拒绝，POST继续旧业务依赖及原执行门。

先在同轮实际审计8个GET与默认reader构造：仅AOS当前已保留数据/明确unknown来源，禁止触发外部商城/Provider/Source探测；如果某reader可能外部请求，该route不纳入本波。先限定root8，辅助/private GET另逐项审计。不改变legacy来源谓词、不伪造runtime-ready/UI session/Owner/审批，不返回mock数据或把None转0。写代码前要记录具体审计与细化方案，再RED、最小实现、专项/累计、真实页面、独立冻结代码复审、Delivery/上下文及下一波。目标是让真实安装状态与read-model缺口正确反映，真实数据/天然首链仍独立验收。

## 第2/8细化（2026-10-13，本轮规则与候选）
Rules：已复习 aos-engineering-delivery、当前01/06 authority2011、231上下文与产品双侧增长方案。唯一m1写者；Task同owner Lease至10:47UTC有效；用户dirty不覆盖；本aos-2不重启。候选一：已登记GET安装读取门（无真实库写、无外部请求依赖）；候选二：已登记预算续期有界consumer（需原真实maker/checker与当前锁再验，不能复用安装审批）。本轮选择候选一。

具体目录：services/aos-api/aos_api/ecommerce_workshop_read_catalog.py；services/aos-api/tests/test_ecommerce_workshop_read_catalog.py；后续审计完成才改services/aos-api/aos_api/routers/ecommerce_workshop.py。

已实际复核：Analyst SourceReadiness只读本库meta_pipeline/meta_source/meta_schedule_run/ecom_object/obj_instance/capability及本地policy文件，无源探测；Customer读本库保留自然run/count；ContentCampaign read_snapshot使用read_connect_factory；Creator各list使用read_connect_factory；TaskCockpit read_core显式REPEATABLE READ READ ONLY。Media根read还经过lifecycle、publish._compose及多个list/get，仍需对其完整传递调用作审计；Operations各本库reader亦需补全。不能因方法名为read就宣称无副作用。

本轮先实现独立适配器，尚不接任何HTTP route：原legacy get_readiness成功原样保留；仅AssetNotFound才查显式selected安装目录；完整复用原签名/锁/hash/角色/marking/撤销检查；selected fallback要求每个声明dataScope都有本安装同lock的DataScopeGrant，禁止只凭module.permissions宣称授权；非object/capability/aip未知或INSTALLED_ASSET_READONLY的其他blocker均拒绝；不提升disabled/readiness、不缓存安装。返回not found隐去未授权模块；原目录、POST及服务reader无改动。专项包括真实本地bundle解析fixture、无scope、撤销、跨tenant、hash漂移、legacy错误不回退和legacy成功不改变。此阶段只证明读取门候选，不证明HTTP数据/8页面/首链。最终route仍待安全审计和单独RED。

第3/8：8缺模块RED已复现后新增纯读取适配器；第4/8：专项与原目录、runtime目录及原HTTP邻接结果见verification-candidate.json。路由字节与HEAD一致，未激活GET、未重启、未改真库、未运行Provider。Media committed HEAD传递调用已按精确方法/hash提取，仍需复核_bundle/_view/_decision/_job等递归helper，不可把调用提取当无效果证明。第5～8步及HTTP接线仍待继续；Task保持ACTIVE，不声称页面或业务恢复完成。

用户新指令：完成当前步骤后移交新对话。候选适配器独立冻结复审r1 PASS已严格消费，限定候选与66项邻接，execution_authorized=false。本步精确提交后形成移交边界Delivery，HTTP root8接线、完整递归审计、原生只读与浏览器及发布仍全部待办；不把候选交付称整波/经营链完成。交接后只读核对新写者与Goal/提醒迁移，旧对话不再启动另一研发波。
