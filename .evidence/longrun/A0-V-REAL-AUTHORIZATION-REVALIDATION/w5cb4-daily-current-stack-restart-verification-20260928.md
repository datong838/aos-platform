# W5CB4 2026-09-28 最新代码／当前数据卷重启验收

## 当前启动事实

当日 m1 最新 HEAD `338bc7b0`。先用当前源码 `a0v_current_preview_http.py` 做只读前置，返回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：数据库 `aos_current_preview_20260927`、版本 `a0v_106`、唯一 installation approved、四包 published、Runtime binding 0、签名树 exact。旧 API PID 14052、Vite PID 13984 精确 TERM；只重启 `colima-aos-extension/aos-a0v-recovery-pg` 容器，命名卷仍为 `aos-a0v-recovery-pg-data`，未删除/替换。重启后立即一次 `pg_isready` 尚无响应，随后重新读回接受连接；未进行任何业务重试或写入。

最新代码 API PID 17435 安全启动，Vite 8434 由既有守护恢复为 PID 17408；8080 OpenAPI 与 8434 工作台均 HTTP 200。启动器明示 `migrationMode=disabled`、Runtime Host 0、workers 0；18181 无监听。浏览器真实 reload `/workshop` 后读到“当前有效安装 0 个／模块未安装／暂无可见工作台入口”，符合当前 Runtime binding 0 的禁入，不将页面 200 误报为八页可用。

## 未通过门和下一步

当前源码已含 a0v_107，但当前权威库仍 a0v_106；D01 选择写路径只在隔离 PG 验证，不能在当前实例调用。C2b 原链＋现时来源＋AgentRun Owner 联合正向和 BG-00 合法 Skill/Capability/模型/职责配置仍未完成；Cron、自然 worker、Provider 继续关闭。每天重启是发现漂移与自检门，不替代真实安装、业务 Receipt、预算和审批验收。下一波继续首链最小合法配置/产品入口；不读商城源、不回放旧 12 Run、不删卷/备份。
