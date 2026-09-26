# W5CB4 P2g 第十六增量：后半段自然消费者默认关闭接线

- 基线 `m1@5e8956d2`。文件改动仅限 `main.py`、正式 EffectReview 与待治理候选消费者、三份专项测试。第一段反馈 worker、九操作 Host、HTTP 路由、迁移和当前实例配置不变。
- RED：新启动专项因 `_start_feedback_downstream_workers` 不存在而导入失败。GREEN：第二段 improvement、正式 EffectReview、第三段 memory candidate 分别由独立 `AOS_ECOM_*_WORKER_ENABLED` flag 控制，缺省均 `DISABLED`、无 task；任一 flag 无效、无 ACTIVE Runtime Host 或独立 runtime DSN 不可用时，启动前 `FAILED_CLOSED` 且不留下任务。启用时挂入 app 任务表，Host stop 可终止；运行中 unknown/异常或无 stop 的意外返回都 `FAILED_CLOSED`，不自动重启/重发。EffectReview/候选各自有界 `serve`，每轮只用 `org-org/dev-project`、读取 Host 状态，`Unknown` 从 batch 穿透到任务；`dev-org` 不作为业务 scope。
- 专项 `33 passed, 7 warnings`；相关电商扩展与 AIP Memory Store 累计 `981 passed, 191 skipped, 9 warnings`，跳过不计成功。`compileall`、`git diff --check`、Alembic 单头 `a0v_106` 通过。纯后端启动门没有适用浏览器验收对象。
- 只读现场：本地 `.env`/`.env.local` 未发现三个新 flag 的显式启用值，8080 未见监听；这不等同全机部署证明。未修改环境或启动真实消费者、未读商城源/调用 Provider/重放旧 Run。隔离测试里的 Host 和 DSN 是受控接缝，不能替代当前真实签名安装与自然周期观察。
- 方案/代码复审：第二段原有 `serve` 复用；正式评估/第三段新增 `serve`，共同启动门先核 flag/Host/身份，再构建并调度，启动即失败时清理新任务。三个阶段按持久 checkpoint 串行自然路由，任一未知提交边界不会被消费者吞掉。仍未证明总控中文回流、当前安装授权、真实来源、Wiki 治理批准或业务效果。下一波做总控只读投影及浏览器验收；第二段成功提交的独立连接回读可作为激活前专项补强，不可据此打开当前实例。
