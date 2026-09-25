# W5c8y｜PG-only 启动前宿主 actor 与纯 HTTP 配置门审计

## 上位边界

承接 W5c8x `m1@ce8cf684` / AOS-000686：真实 VM Running、Docker 运行容器 0、8080 launchd job 缺席、PG/HTTP 端口空闲。W5c8v/w 只证明容器 restart=no 与 VM 离线启动路径；宿主 `com.aos.prime-agent-safe`、Web 8434、memory-health 等仍可能在真库上线后行动，**不能直接启动 PG**。旧 8080 plist 缺零执行旗标，严禁 bootstrap。

## 本波文件级与只读步骤

- 仅新增 plan、audit、verification，不改生产代码/服务/数据库；先提交本 plan。
- 只输出宿主 AOS 作业 label、PID、进程 basename、监听/连接端口；对相关 launchd plist 仅做布尔白名单判定：是否携带 AOS DB endpoint、Runtime Host/worker/Cron 开关、是否为 API/worker 可执行。绝不输出完整 plist、Env、DSN、命令行或凭据。若安全读取无法保证，STOP。
- 复核真实 VM `docker ps` 0、PG exited、8080/18181/18435 free。仅静态核对 `a0v_product_controlled_api.py` 与对应测试对纯 HTTP 模式的 Cron=false、snapshot worker=false、Host=0、migration disabled 配置边界，不启动 18181。
- 若有仍存活宿主 actor 可在 DB 恢复后自主运行，下一波先隔离该 actor；若无，下一波设计唯一 PG 容器启动与纯 HTTP 读回。任何未知保持真库 stopped，不以测试/计划冒充运行态证明。

## 九步与退出

1. 复习 AT/AS、W5c8x 与产品/技术 no-effect 边界。
2. 本方案先提交。
3. 新鲜 VM/容器/端口/宿主 job 只读前检。
4. 最小白名单 host actor + HTTP 配置审计；不启 PG。
5. 专项静态/只读核验；既有测试不冒充本波实测。
6. 累计回归复核无代码变更与现有证据一致。
7. 8080 API 离线，浏览器验收不可执行；方案/现场一致性复审。
8. audit/verification、m1、D-waves/AOS CAS/Prime。
9. 自动下一波：依据 actor 结果先隔离风险或计划 PG-only 启动；不能确认则冻结并查因。

230 L0 挂起、dev-org 仅零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push、不读商城源。
