# W5c6b Store 物理 DB/角色只读可行性核验（2026-09-25）

方案 `c7a0317f` 先行，只读诊断与合同 `e83bd9cf`。真实 Store、DB schema、Host flag 均未修改。

## 九步证据

1. 复习 controlled `_authoritative_store` 与 `runtime_worker_connection` 的同一 runtime DSN、Store `_apply_transaction_scope`、`a0v_094` 权限及 W5c6a 独立 effect 边界；另确认 Schedule/Recovery 根仍未给 Completion 传 lease。
2. 仅新增 `scripts/a0v_w5c6b_store_identity_feasibility.py` 和纯函数合同 `test_a0v_w5c6b_store_identity_feasibility.py`；没有生产 Store 接线。
3. 诊断在只读事务中核 metadata 与 Store 物理指纹、同一 runtime 登录、Store 事务的 `aos_runtime`、`a0v_094` 函数存在/执行权限；只输出布尔值，未打印 DSN/秘密，未调用 lease acquire/fence、Store apply 或源读取。未知指纹直接冻结。
4. 新纯函数专项 **3 passed**；首轮直接调用没有 runtime 身份配置而 `FROZEN_STORE_IDENTITY_AUDIT/OBSERVATION_RuntimeError`，读回确认未配置环境，不将其误记为真实库缺陷；随后用既有 0600 受保护 runtime 身份文件只读复跑。
5. W5c6a+b 无效应组 **7 passed**（无隔离 PG，按 `--confcutdir` 跳过全局数据库 fixture）。W5c5k–z 围栏/结构 39 passed 为上一波历史基线，本波未重跑。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行或冲刷队列，临时页面/Vite 已关闭。
7. 真实审计 `STORE_LOCAL_FENCE_NOT_READY`：`samePhysicalDatabase=true`、`sameRuntimeLogin=true`、`storeRuntimeRole=true`，但 `fenceFunctionPresent=false`、`fenceExecutable=false`、`storeEffectAuthorized=false`。实时关闭门禁仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`closureAuthorized=false`；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。不得接线 Store effect、关闭旧组或重发旧 attempt。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6c：仅在隔离 PG 迁移 `a0v_093/a0v_094` 后检验 Store 自有事务内的角色/围栏适配；真实 DB 未迁移前始终 no-effect。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
