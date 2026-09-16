# SC4-5L6Y5F4 U：当前就绪代宿主冷启动接管验证

日期：2026-09-17

## 结论

代码补齐仍在合法短租约内的当前就绪代接管。目录把未交付首次准备与可接管 ready 代标成不同 mode；接管路径重新锁定 active Installation、唯一 ready/enabled/unfenced binding、已成功 runtime-apply、当前权限/条件、签名 claims、完整未释放资源与原 container identity，原子续 180 秒租约后附着原停止容器。该路径不创建 generation/resource，不重放 prepare/verify/configure/enable，不制造 outbox。

容器附着前必须精确匹配 ID、平台生成名称、owner label 且处于 stopped；注册与 heartbeat 仍走原签名协议。接管 Job 从创建时即为 verified，健康检查后可使用原续租事务。关闭或附着失败仍由 ResourceJournal 精确记录释放/uncertain 并栅栏，不以缺失推断释放。

## 验证

- 运行时目录、scheduler、worker、owner、OCI、host、production composition、live directory 与 invoker 邻接：168 passed。
- 额外 consumer/目录定向首轮：40 passed，数据库夹具因本轮未注入测试 DSN 而 16 skipped；未把 skipped 记为 PG 通过。
- 当前真实 `org-org/dev-project` 使用 runtime identity 执行新目录 SQL，结果为空元组。真实 L binding 已是 `enabled=false / operation_fence=true / observed_state=unknown`，三资源均 released，因此未被错误接管，主库零业务写入。
- `compileall` 与 `git diff --check` 通过。

## 边界与下一波

本波解决“进程重启但资源尚在有效接管窗口”的产品缺口，不复活已过期或已释放代。当前 L 仍需新 generation 受控重建；不能把 U 的代码绿色当成真实首链恢复。下一波 V 复用现有安装生命周期建立新代，恢复 exact 配置与 enable，重载 Host 后确认唯一 live target，再开启短时自然商品任务验证 ingress → occurrence → Case/Run。
