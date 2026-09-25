# W5c8j｜同事务源组哈希门禁验证

## 判定

本波为**负例与替代设计完成，完整对账原型 STOP**。先行方案 `m1@33a5413d`；真实 `aos-extension` 停止、真实库未迁移、8080 未重启。无新 ACK 函数、无新 EXECUTE、无 Worker 接线；真实 closure/no-authority 不变。

## 第 1/9—9/9 步

1. 复习 W5c8h/i、`a0v_045/050/094/096`、Locator 与 Python `_digest`；AOS-000671 与 m1 对齐。
2. 文件级哈希门禁方案先提交 `33a5413d`，禁止写半安全 ACK 入口。
3. 专用 `aos-a0v-test-only` PG 中三个 binding/manifest 形态先 RED：`jsonb::text` 的 SHA-256 全部不等于 `_digest`（3 failed in 4.47s）；简例是 PG 输出额外空格。
4. 仅把该错误假设固化为负例回归，并试验精确 canonical 文本见证：三项的文本 SHA-256 与 Python 相等、`text::jsonb` 与保存 JSONB 相等。**没有**声称历史组已具此见证或 SQL 全域算法等价；未写 ACK SQL。
5. 专项 `3 passed, 7 warnings in 3.88s`；W5c8i 撤权/Worker/Store 加本波测试累计 `24 passed, 7 warnings in 10.32s`。`py_compile`、`git diff --check` 通过；disposable `aos_test_*` 库 0。
6. 本地 8080 health HTTP 200，但 IAB 打开 `127.0.0.1:8080/v1/health` 被浏览器客户端阻断；上波真实工作台租户目录亦不可用。浏览器验收**未通过**，未进行业务操作或读取商城源。
7. 复审详见同目录 audit：JSONB 文本不是 Python canonical 原字节；新见证需原写事务生成、历史回填逐行比对、不可变/大小边界和 Host→Delivery 同事务验证。三样本只证明候选可行，不证明生产兼容。
8. verification 与负例测试落盘并提交；D-waves、AOS CAS、Prime 回读另提交。继续 `automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`。
9. 自动进入 W5c8k：先方案化**历史源组精确 canonical 文本见证与隔离回填拒绝矩阵**，再评估是否具备完整同事务 ACK 的必要证据。若不能无歧义回填，按 STOP 分流；不得迁移真实库、接 Worker、重发 unknown attempt。

230 L0 挂起，商城源不读，dev-org 仅零 canary，m1 单写不 push、不动其他分支。
