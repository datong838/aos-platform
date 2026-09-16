# SC4-5L6Z-Q｜游标安全 API 运行态验证

2026-09-17，代码 `b4aee36d`。旧 18181 PID 336 的命令精确匹配 `a0v_l_natural_api.py serve` 后收到 TERM 并退出；新 PID 27220 使用当前有效 `A0V-NATURAL-CHAIN-MAIN-UPGRADE-20260915` m1 租约启动。只替换 API，未拉起第二 Host。

启动 preflight 为 GREEN，sourceCalls=0、runsCreated=0；运行开关保持 migration disabled、QYH Cron enabled、snapshot worker independent、extension Host in API disabled。worker 为 IDLE/alive，`hostInThisProcess=false`。18181 health/ready、5173 ontology、8434 恢复入口均为 HTTP 200。

对 `sch-p02-qyh-controlled-20260913-v1` 发送真实 `PATCH {"enabled":false}`：HTTP 200；请求前、响应和数据库读回的 `lastRun.id` 均为 `scr-4eda5462575a4740`。运行记录保持 13 条，修复 Receipt 保持 1 条，没有新来源运行或外部副作用。由此关闭“代码已修但运行进程仍旧”的退出项。

启动器与原 profile/锁专项：4 passed，9 deselected。下一波只建立 Q 新代和新自然窗口，不复用 P 历史权威。
