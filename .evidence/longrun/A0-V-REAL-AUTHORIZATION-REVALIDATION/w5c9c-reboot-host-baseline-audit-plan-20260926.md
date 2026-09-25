# W5c9c｜重启后 knownHost 观察器拒绝与拓扑缺口审计

## 上位边界

承接 W5c9b `m1@ca62647e`/AOS-000690：定义 rev4 disabled、原 attempt failed/PermissionError、12 Run stalled-running、原组 closure Receipt 0；W5c5g 组合门的 knownHost 子观察器在电脑重启后抛 ValueError。严格 24h 到线也不授权真实关闭。当前唯一 PG + 18181 Host=0/Cron=false/snapshot=false；旧 8080 job 继续 bootout。

## 文件级与只读步骤

- 本波只新增 plan、audit、verification，不改生产代码/数据库/服务；先提交 plan。
- 新鲜核唯一 PG、18181 租约/PID、8080/job、原 Run 数。分解 `a0v_w5c5c_host_role_topology.observe()` 的 baseline、宿主进程快照、注册角色只读 SQL 三段，**仅输出段名/异常类型/聚合**，不打印 `ps args`、plist/Env/DSN/凭据。所有 DB 查询必须在 READ ONLY 事务；不为拿 GREEN 改历史 PID 基线或扩大查询权限。
- 识别 ValueError 是历史脚本自身基线漂移、进程解析，还是角色观察失败；对比 W5c5g `topologyComplete=false` 设计与受管目录边界。即使能解异常，也不能把本机已知 launcher 静默等同全机 Host 穷尽。
- 时间门到线前后可作一次只读 W5c4t 分类回读，绝不调用 real closure Owner/key、run_definition、迁移、Worker、回填/ACK。

## 九步

1. 复习 231/231-9、W5c5c/g、W5c9b 及重启现场。
2. 本方案先提交。
3. 新鲜服务/租约/PG/原状态只读前检。
4. 三段白名单诊断 knownHost ValueError；未知即冻结。
5. 专项纯只读对账与段级结果复核；无代码测试不冒充。
6. 累计回归仅引用上一波已有测试范围。
7. 8080 业务浏览器离线，不填 GREEN；方案/代码一致性复审。
8. audit/verification、m1、D-waves/AOS CAS/Prime。
9. 自动 W5c9d：若是脚本静态假设失效，先方案修只读诊断；若为全机拓扑缺口，先设计独立权威来源。任何一种都不直接执行原组关闭。

230 L0 挂起、dev-org 零 canary、unknown 不重发、m1 单写不 push、不读商城源。
