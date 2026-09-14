# SC4-4b2 正式事件自动初始化验证

日期：2026-09-14；基线 b890ce91，m1单写者，不push。

## 结果
正式ProductEventAnalysisService.handle从无业务Run进入，共用原Run创建，当前Context/Compile/Preview/Action草稿及来源派生初始化门，最后sealed Host绑定实际paused TaskRun和不可变AnalysisRuntimeReceipt。原claim重复返回同一Receipt，没有额外TaskRun/CompilationReceipt，不生成冒充人的ActionApprovalEvent。

实际分派锁暴露两项原缺口：a0v_028只接受9操作但事件控制组为10；外层journal与分析Host的请求摘要口径不同。新增a0v_044严格兼容原完整9或原9+event_control，缺项/未知拒绝，原会话/租户/serializable门不变。分析journal使用原严格协议验证后的requestHash；数据库不可变比较保持。

## 新鲜验证
- 修复前实际十操作组失败，另三组测试通过；修复后9/10/缺项/未知四组通过。
- 完整入口在最终journal处复现UniqueViolation；摘要修复后6项通过。
- 最终累计：82 passed，7条既有警告，41.77s。覆盖formal入口/失败回滚/错误协议摘要、原事件当前守卫、无跨await事务、普通适配器、分析Host、数据续跑、专用初始化门。
- 原raw Host绕过编译的严格xfail改为明确拒绝测试；完整handle作为正向证明。
- AR2-7：1904模块、183分类、93迁移，五类错误均空；git diff --check通过。
- memory validate：GREEN，1100 Delivery /1084 Task /2700 events；项目AOS-000573。

## 边界及风险
全部在18432的临时隔离数据库运行；技能发布/Context/编译/Task/回执是真实Store，来源可用性、角色/能力、安装计算仍有明确fixture。没有在主租户新建业务Run，没有模型调用，没有迁移或部署主安装。此结果不等于真实首链完成。

a0v_044对应子Lease A0-V-SC4-DISPATCH-GROUP-10，只变函数、不写业务数据；降级恢复9操作规则，含10操作的组会被阻断而不删数据。普通bootstrap恢复仍拒绝；后续必须提供当前经营/数据授权，不能复用初始化许可。

## 下一波 SC4-5
复核现有数据需求与分析恢复路径，先完善当前续跑承接方案，再接实际来源/Requirement/Fulfillment/Checkpoint到受控恢复；保持通用resume拒绝，增加过期/错接/回滚验证。其后新包候选/主安装更新、真实首链、八场景及连续观察。
