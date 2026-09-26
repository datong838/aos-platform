# W5cag｜旧 PG skipped 当前风险措辞校准方案

## 上位与证据

231 A0-V/BG-00 仍冻结。AOS-000730 的 34 项 incomplete 中第 21 项仍写“old ingress PG 12 skipped”，第 22 项写“old Single/Object PG skipped”；这是 W5c5x/y 的历史测试状态。W5caf `29f2bf6a` 在同一 18432 隔离会话中三文件 24 passed；当前 collect 精确为 ControlledSnapshotIngress 12、ControlledExecutorIntegration 4、SnapshotGroupObjectExecutor 8。W5cae 的 16/16 是另一次旧 Journal/CompletedInput 会话。历史 skipped 记录必须留在 Git，不能倒改。

## 文件级/动作

- 只读复查 W5c5x/y 和 W5caf verification、当前 authority incomplete 两条及三文件 collect；不改任何生产/测试代码，不启动 PG 或真实 worker。
- 用 authority CAS 把两条当前风险改写为：旧 PG 当前 12/4/8 通过已证，但 **Single Executor/Object/Link/Retirement 的当前生产租约传递、Store 跨独立提交 effect、真实库迁移/全机 Host 排他仍未证**。不删除风险条目，不改变 next gate/硬边界。
- 本目录 audit/verification、AOS 项目上下文/Prime 受管记忆更新与精确提交；无关脏文件保留。

## 九步/停止

1. 复习 231、W5c5x/y/W5caf、current authority。2. 本方案先提交。3. 精确旧新文案审计。4. 无代码最小 CAS 修改两项。5. `memory validate/status` 累计核对 34 项数量与其他 32 项完全一致。6. 18181 浏览器只读，8080 不具真实验收条件。7. 复审历史 skipped 与当前 GREEN 的时间语义、真实 effect 禁令。8. verification/上下文/Prime 落盘提交读回。9. 下一波回外部门禁与剩余可安全补证项。

任何 authority CAS 版本冲突先冻结，不自动重试；不得把旧夹具 GREEN 写成真商城源/原十二 Run/正式业务效果。230 L0 挂起、dev-org 零 canary、m1 单写不 push。
