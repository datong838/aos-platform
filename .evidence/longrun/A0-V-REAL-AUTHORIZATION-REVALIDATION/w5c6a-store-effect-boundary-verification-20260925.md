# W5c6a 跨 Store effect 无效应边界合同核验（2026-09-25）

方案 `4e0c694a` 先行、derived effect 补证 `4a34bec0`，合同实现 `a1800325`。生产代码、Store schema、真实 DB/Host 均未修改。

## 九步证据

1. 复习 Single base/derived、Link、Retirement、Dataset cache 和 Store `_apply_batch` 原提交/回执顺序，核 W5c5z metadata lease 链路。
2. 仅新增 `test_a0v_w5c6a_store_effect_boundary.py` 无效应合同；未接线 Store lease，未改生产代码。
3. 合同固定 Single base metadata commit→Store apply→metadata readback、derived 每条独立 Store effect、Link/Retirement preparation commit→Store apply→readback、Dataset receipt→内存 cache；Store `_apply_batch` 独立 SQLAlchemy `engine.begin()`、原回执 replay，原 Store API 无 Host lease 参数。
4. 新专项 **4 passed**。首次因隔离测试库已停而在 pytest session setup 报 4 errors，断言未执行；恢复隔离库后重跑全绿，没有隐瞒环境失误。
5. W5c5k–z 加本波合同 **43 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。此前主组 162 与定义合同 24 为历史基线，本波未重跑。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行或冲刷队列，临时页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。合同仅证明风险边界，不构成 Store 原子排他或真实关闭授权；不得重发旧 attempt。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c6b：只读核 Store 物理 DB/连接身份与事务内 lease guard 可行性；不满足则设计 receipt-first 替代，禁止盲目接线。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
