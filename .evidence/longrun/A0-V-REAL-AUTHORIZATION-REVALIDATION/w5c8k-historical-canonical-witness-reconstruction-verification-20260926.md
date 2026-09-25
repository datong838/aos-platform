# W5c8k｜历史源组 canonical 字节见证重建验证

## 判定

本波**隔离 PG 与纯函数实现 GREEN，真实历史回填/对账授权未完成**。先行方案 `m1@a03fcdd0`。新增模块只对读回的 JSONB 与已存双 hash 复算精确文本并 fail-closed，不读源、不写数据库、不供 Worker 自动执行；原有 `a0v_096` 仍只在隔离库 head 测试，真实库未迁移。

## 第 1/9—9/9 步

1. 复习 W5c8h/i/j、原 `_digest`、`a0v_045`、claim/input 写入与 Locator，核 m1/AOS-000672、专用 PG；真实 profile 仍停止，原 12 Run 当前值未知。
2. 文件级方案 `a03fcdd0` 先提交，限定纯计算、隔离测试、无 ACK/迁移/Worker 接线。
3. 新测试先因模块缺失 RED（collection `ModuleNotFoundError`）；实现后一次 RED 暴露非有限数未归一包装，按拒绝语义修正。
4. `pipeline_snapshot_group_canonical_witness.py` 对 JSONB dict 以原 Python canonical 参数重新序列化，限制单对象 65536 UTF-8 字节，并交叉比对已存 `sha256:` 与 `_digest`；非法类型/哈希、NaN、Decimal、过大文本或 JSONB 数值归一化导致的 hash 漂移均拒绝。返回文本见证而非授权布尔；不改现有 `_digest` 或任何写入/Worker 路径。
5. 轻专项 `6 passed, 1 deselected, 7 warnings in 4.49s`；真正保存源组全链只读测试 `1 passed, 7 warnings in 115.26s`，源调用数维持 1。W5c8i/j 相关短累计连本波 `30 passed, 1 deselected, 7 warnings in 10.76s`；`py_compile`、`git diff --check` 通过，disposable `aos_test_*` 库数 0。
6. 本波无 UI 改动；8080 health 仍可读 HTTP 200。上一波 IAB localhost 被客户端阻断，真实目录此前不可用，本波未取得浏览器业务页验收，**不可判真实浏览器 GREEN**；无业务点击、商城源读取或队列冲刷。
7. 复审：通过的是**限定夹具的 JSONB 读回重建**，不证明现网历史所有行都可回填；`1e20` 样本在 JSONB 往返后与原 Python hash 不同会冻结。模块不核 PREPARING/Occurrence/Origin/Host/双 Receipt，不能单独作为对账 authority；真实库未扫、未迁、Worker 未接，原 unknown 不重发。
8. verification 与代码同一 m1 提交；D-waves、AOS CAS/上下文与 Prime 强一致回读另提交。`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false` 保持。
9. 自动进入 W5c8l：先独立方案设计新不可变 canonical 文本见证字段、历史逐行只读扫描与拒绝式回填/迁移，隔离 PG 覆盖不匹配、缺行、并发和回滚；无完整证明不得建 ACK 函数或动真实库。

230 L0 挂起，商城源不读，dev-org 仅零 canary；m1 单写不 push，不动其他分支。
