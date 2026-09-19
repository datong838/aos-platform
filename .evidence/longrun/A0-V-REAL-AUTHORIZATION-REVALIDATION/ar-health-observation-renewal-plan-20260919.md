# AR 健康观测续租瞬时锁竞争修复方案（2026-09-19）

## 1. 上位目标与边界

本修复服务于栖月汇 `org-org/dev-project` 真实首链的可恢复运行，不把测试通过当作经营闭环完成。继续遵守：

- 单写者 `m1`，不 push；230 L0 单独授权事项继续挂起。
- 健康探测必须来自仍被 Owner 持有的完整资源组，三秒新鲜度门槛不放宽。
- 每次健康过期事务必须已经结算并回滚，才能重新探测；不得复用旧观测、不得绕过权限、条件、租约或 binding CAS。
- 重试必须有固定上限；超过上限仍按现有路径停止 Owner、fence binding、释放资源。
- AR 已被 fence，definition rev67 已禁用且没有 execution attempt；修复阶段不重跑 definition、不发送未知结果。

## 2. 生产证据与根因

AR runtime-apply operation `369824f3-c122-4dd3-81f8-aab57fcf3710` 在 07:15:15Z 至 07:23:30Z 连续完成 10 次续租，健康观测到事件落库通常约 0.3–1.7 秒。下一轮续租先在 `PreparationOwner.renew` 的首次 commit 抛出 `HealthObservationStale`，重新探测后的第二次 commit 仍因锁等待超过三秒而抛出同一异常。现有实现只允许一次重探，第二次异常使 Owner 停止；07:24:43Z 三项资源均被安全释放。

结论：三秒新鲜度检查本身正确，缺口是瞬时锁竞争可能跨过两个连续三秒窗口，而 Owner 只容忍一个窗口。

## 3. 文件级施工清单

1. `services/aos-api/tests/extension_runtime/test_preparation_owner.py`
   - 把已有单次过期测试扩成连续两次过期、第三次成功。
   - 新增超过固定上限仍抛错、Owner 关闭的失败封顶测试。
2. `services/aos-api/aos_api/extension_runtime/preparation_owner.py`
   - 仅在 `HealthObservationStale` 时重新探测并重试。
   - 最多允许三次重新探测（初次提交加三次重试，共四次提交）。
   - 每轮前继续检查 stopping、cleaning、task done；其他异常原样失败。
3. 本文与 AR 波次证据
   - 记录专项测试、累计回归、真实失败 generation 退休与直接后继结果。

## 4. 退出条件

- 连续两次 stale 后第三次使用新健康观测成功续租。
- 连续四次 stale 时不再重探，错误仍触发原有 fail-closed 关闭。
- 既有 Owner、lease renewal、runtime host 相关专项测试全部通过。
- AR 通过正式 disable/retire 路径退休，资源与路由无悬挂，`dev-org` canary 为零。
- 新后继只能经完整 apply/verify/configure/enable/cutover 建立，不能复活 AR generation。
