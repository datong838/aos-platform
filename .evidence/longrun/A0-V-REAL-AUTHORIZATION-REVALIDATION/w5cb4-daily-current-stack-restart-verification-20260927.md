# W5CB4 每日最新代码／当前数据卷重启首次验收（2026-09-27）

## 结论

按 `w5cb4-daily-current-stack-restart-plan-20260927.md`，以 m1 `a615c552`（提交 22:30:57 +08:00）之后的新进程重启当前 AOS 安全预览：PostgreSQL `colima-aos-extension/aos-a0v-recovery-pg` 只重启该精确容器，原命名卷 `aos-a0v-recovery-pg-data` 未删除/替换；API 8080 新 PID 8783（22:42:34），Vite 8434 新 PID 8459（22:41:55）。前端旧 PID 1270 精确 TERM 后由既有守护机制自动重起 8434；手动启动尝试发现 8434 已占用，产生的临时 8435 已立即终止，最终只有 8434。旧 API PID 90285 精确 TERM；新 API 用当日源码、同一签名 Receipt 和现有 `a0v_current_preview_http.py` 安全启动。18181 无监听，Cron/各 worker false、Runtime Host=0、迁移 disabled。

库重启的立即只读检查曾因 PostgreSQL 尚未 ready 返回 SAFE_BLOCKED，无写入或重试业务动作；随后 `pg_isready` 成功，独立读回 `aos_current_preview_20260927`、role `aos_app`、566 public 表、`a0v_106`。安全预览前置再次得到 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：唯一 installation `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` approved、四包 published、Runtime binding 0、签名树 exact。未查询商城源数据，也未删库/卷/备份。

API `/openapi.json` 200，前端 `/` 与 `/workshop/cockpit` HTTP 200；后者不是有效工作台业务路由，不能据 200 计成功。浏览器真实打开 `/workshop`：已安装电商工作台 0 个、导航暂无可见电商入口；打开 `/aip/model-runtime`：数字同事 0/6 可自动执行、绑定 0、当前租户无模型路由、供应商/策略/价格等均 0，草稿入口保持未选择、未激活。这是预期禁入，不是八工作台功能验收或自然首链完成。

## 未关门和下一步

**最新源码运行≠当前库完成 a0v_107 迁移。** 现有预览启动器明确要求库 a0v_106 且迁移 disabled；新 D01 B/C1 表只在隔离测试库证明，当前库尚无这些表，不能从当前实例调用完整包选择。旧容器 `/backup` 的 bind 来源在 macOS 主机侧未见，不能视为独立备份；迁移前需按新 D 波找不读取商城源内容的备份/恢复路径，并更新启动器版本门，经测试、独立读回再重启。每日 09:00 已创建附着当前任务的检查门，**当前 Goal 不等待它才推进**。下一研发切片继续 C2 联合证明，同时并行排序 BG-00 最小合法配置；用户原有工作树文件保持不动。
