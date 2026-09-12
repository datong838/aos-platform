# P01 正式计划验证方案

2026-09-13，m1，基线80171540。沿用当前A0-V授权和主Lease；不push，不进入230 L0，不发布外部内容。

先新增 scripts/a0v_p01_current_preflight.py，复用已有只读准备逻辑，固定当前Niushop1.4根、安装afd792de-e85e-4680-86d0-c83404824fb3@7和真实HTTP主体user:dev。从当前签名注册资源校验并派生字段hash，不沿用旧安装/旧mapping。执行当前Owner完整_guarded只读检查，无审批/源查询/业务写。之前临时只读检查误用artifacts公开属性，实际为_artifacts，未发起源查询；保留失败证据，修正准备工具。

准备通过后通过正式HTTP source-selection-approvals、runtime-control-approvals，以每步固定幂等键保存exact引用；创建唯一P01计划，初始disabled，经schedule-control-bindings绑定再启用。API响应需数据库事实复核。Cron继续关闭，只手动一次正式run。源范围ns_site/site_id=1、11非敏感字段、100行上限、30秒、一次源调用、15分钟审批窗口。结果不明不得换键重试源，先核对原Run/Claim/Journal；已保存源结果仅原Run恢复。

成功判据包括原始Journal、Receipt、对象/数据集落库、租户隔离、重复运行/恢复不越权；HTTP200和302表预览均不算首链成功。失败时保留具体阶段与事实，修产品前补方案与测试。P01成功只证明受控数据接入，后续经营首链/八场景/观察仍独立验证。本地API仍采用原诊断元数据身份，生产Web身份收敛为发布前待办。

18:17Z当前检查：user:dev持久化owner不属于冻结的apply角色集合，DutySeparationRequiredError正确拒绝。保留该负向结果，不改成员、不放宽角色集合、不向请求体塞actor。只读工具增加两个固定actor选择（默认user:dev，另一项为已存在的a0v-ecommerce-growth-1.4-runtime-owner），先验证现有运行管理员当前权限，再通过已启用的本地开发认证接口取得该主体的签名开发令牌；令牌仅内存，不输出。此路径明确为开发身份验收，不能冒充生产认证、不能算默认owner操作已通。
