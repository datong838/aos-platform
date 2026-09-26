# W5CB4 P2f-b 第 4/4 步子项｜内容预审安装前只读预检

- 依据同目录 `w5cb4-p2f-b-controlled-content-eval-bootstrap-plan-20260927.md`；本文件仅记录 bootstrap 第一子项，不把 P2f-b 或 W5CB4 记为完成。
- RED：新增预检测试因无模块无法收集。GREEN：`ecommerce_content_pre_review_bootstrap.py` 在一事务只读核 exact `a0v_105`、目标 Graph、两专用 Suite 及同 subject 合同库存；全空只标 `INSTALLABLE` 候选，完整库存还须 `require_current_content_pre_review_gate` 全链核验才标 `INSTALLED`，局部/多义为 `RECONCILE_REQUIRED`。此入口无写、无重试、无 Worker/Provider。
- 专项 `10 passed`；内容邻近累计 `268 passed, 9 skipped, 7 warnings`。9 skipped 为专用 PG opt-in 测试，不列作通过；warnings 为已有 Pydantic/Starlette 提示。`git diff --check` 通过。无 UI 改动，浏览器验收不适用。
- 当前实例只读：经指定 Colima 容器与数据库身份核验的 `aos_meta_head` 为 `a0v_092`、目标 Graph 0、内容主体合同 0；新预检实测 `SCHEMA_BLOCKED(a0v_092)`。这证明当前实例不能安装，不授权在此步迁移或写入。未读商城源数据，未动原 12 Run、230 L0、Provider 或外部发布。
- 余项：按方案逐独立 commit 的正式 API 安装执行器、未知提交冻结/只读对账、隔离 PG 正反验证、当前实例迁移/安装边界仍待完成。`INSTALLABLE` 仅表示这三类主库存为空，不代表可无条件安装或自动开启 Worker。下一子项先复核 Dataset/Receipt/幂等键和各独立提交边界，再编写安装 executor 的 RED。
