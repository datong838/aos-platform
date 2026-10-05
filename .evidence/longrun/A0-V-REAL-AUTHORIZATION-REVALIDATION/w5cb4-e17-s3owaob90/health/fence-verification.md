# Health原DML fence实际验证，待单写归属对账

Task `w5cb4-e17-b90-health-fence-implementation-20261005`与fixture Task ACTIVE，Authority AOS-001330；本步骤不是完整b90交付。原机制RED Task已Delivery，保留原red.log及原205684/205685反例。

本次实际隔离PG：test-only Docker context现存aos-a0v-test-pg发布127.0.0.1:5433，原conftest创建/迁移一次性aos_test_*_ti4_test，未指定共享数据库。当前真实142@18435不连接、不迁移、不重启，无Host/worker/Provider/商城源/外部效果。

## 实际结果

- `fence-red.log`：5failed/2passed/7warnings/5.72s，terminal1。实际跨Provider revision写者没有被阻挡、TRUNCATE没有拒绝、未FORCE RLS/trigger函数PUBLIC权限、缺tenant未拒与provider_id合同缺失；不是仅缺模块。
- 修复a143按tenant/provider-id协调、FORCE RLS/最小函数ACL、缺行中性初始化、原INSERT/UPDATE/DELETE双资源协调和有效改变epoch、TRUNCATE拒绝，不复制健康状态。
- `fence-green-r1.log`：7passed/5.22s terminal0。此时含一个仅callable的旧合同测试，不作完整消费者证据。
- `fence-adjacent-r2.log`：13passed/1failed/7.46s terminal1，唯一失败为原table-owner test cleanup DELETE没有tenant GUC；原record_health/Receipt replay业务路径通过。精确fixture追加Task后，仅添加原SCOPE两GUC，没有降低产品租户门。
- `fence-adjacent-r3.log`：14passed/7.72s terminal0；仍含callable旧合同。
- `fence-final.log`：13passed/1strict-xfailed/7warnings/7.72s terminal0。9个Health机制实测与4个原ModelRuntime相邻通过；完整evaluate_binding_in_transaction尚缺，改为strict ImportError xfail明确记录未实现，后续实现XPASS强制替换为完整行为验收，绝非业务拒绝或八facts正向。
- 实测包括跨revision共享阻挡及失败rollback、原40001拒旧SERIAL snapshot、UPDATE old/new资源epoch及noop不抬epoch、DELETE与rollback历史保留、缺tenant/错scope、TRUNCATE拒绝、runtime无直接fence表权限及仅shared neutral初始化。无模拟Provider调用，无真实模型费用。
- 三文件py_compile、限定git diff --check通过。无页面改动，浏览器验收不适用。

`fence-test-cluster-readback.json`：原49旧测试库仍49，三个本次可见新增/迁移role均NOLOGIN/noinherit/无高权/双向成员0/共享依赖0，保留未DROP。没有DROP OWNED或清理旧库/卷。Source init role本次查询名未命中，不根据缺行臆称已清理。

## 单写归属异常与保护

本轮最初HEAD cef84e51；10:42:17存在非本轮发起的25350576提交，包含三个原未提交Health草稿，10:43:48本轮方案提交15a6a019随后成为HEAD。该提交说明至少发生了未归因的共享仓库写入，不能据此推断某个进程仍在写。

App只读回读当前chat active、旧chat notLoaded；PID7351由node_repl60377启动，但其argv为codex app-server --listen，并非codex exec。**不能把该服务进程当已证实第二施工写者，不杀未知进程。**已向用户询问25350576归属及写者是否停止；没有在未知归属下继续写共享代码、重置或覆盖提交。原提交本身声称完整消费者和七健康回归的文字没有匹配本次完整命令证据，不能继承为GREEN。

当前修复仍在工作区，`pending-fence-fix.patch`保护三个精确代码差异；`tested-pending-fix.json`绑定已测代码hash/HEAD/terminal结果。尚未代码commit、代码Task Delivery、authority推进或AOS/Prime同步，不能称收口。plan原完整Task继续ACTIVE。

下一：确认单写归属后，对照已测hash精确提交/Delivery与AOS/Prime上下文；继续完整Source纯核验及正式八facts/原Receipt-CAS-proof命令，保留治理消费锁序与逐表ACL审查。现有helper没有完整业务消费，a143也没有正式evaluator权限，更没有当前142迁移授权。Goal active，自然首链及发布仍未完成。

## 后续安全收口裁决（覆盖上文临时停止提交的操作状态）

后续再次核对HEAD15a6a019及三个已测hash完全一致、仅root agent running，App可见当前chat active/其他已查chat非施工状态；已登记Task/Lease都归本线程，无新的仓库提交。7351只是app-server，不存在据此认定第二代码CLI的证据。未知25350576来源仍待回答，但该历史提交完整保留，根本无需重置、rebase或覆盖它。持续未知来源不能自动撤销用户给本线程的开发授权，也不能把此前口头临时“等待归属”升级成新的审批门。

据此只精确收口本线程已登记并实测的三文件差异及方案/证据；不提交尚未修复的formal helper改动（该文件仍完全保持25350576版本），不动保护九M，不push、不改其他分支。提交时核对已测hash/HEAD，收口后核对精确commit文件集。如果出现新的重叠变更/HEAD竞态则重新对账；来源询问保留供追溯，不作为授权缺失。这是当前可执行的保护措施，不声称所有系统中不存在未来写者。
