# W5CB4 BG00ca｜网络批准消费预检隔离验证

## 基线与范围

按 231/231-5、41、BG00bs/by/bz 与文件级方案，m1 基线 `3c5be7ef`、当前权威库 `aos_current_preview_20260927@a0v_117`，正租户正式网络 Proposal/ApprovalEvent/revision0，Host关闭。本波新增内部 `precheck_network_activation(conn,scope,proposal_id,approval_event_id)`；调用方须提供精确租户事务。函数只读取与锁定证据，不写 NetworkPolicy head/revision/Receipt，不提供 API 路由、执行权或 active 放行。合成成员和批准仅在显式 test-only 克隆 `aos_bg00bx_cutover_testonly_20260930`。

## RED/GREEN 与复审

- 新 PG 测试首先因模块缺失收集失败（exit2）。最小实现后第一次隔离运行暴露 Receipt 为只增表，运行角色 SELECT 但 `FOR SHARE` 被拒；只移除此查询的行锁，不扩大权限。随后显式 clone 专项 1 passed。
- 克隆经正式 Producer/Checker 路径生成一条 R2 approved Event，核 Event 提案版本+1等于当前 Proposal 版本；内部预检返回固定 Proposal 消费键和精确策略 ID/revision/hash。错 Event、跨租户、已有同键 Receipt、head 漂移、当前 checker成员缺失、ApprovalEvent hash 篡改、Egress有效期漂移、审批/提案到期、后续拒绝、maker撤回均失败关闭。所有测试版 head 改动清理、Receipt 插入回滚；预检后网络 head/revision/receipt均0。
- 相邻累计 35 passed/1 skipped；`compileall`/目标 diff检查退出0。当前真实库只读：version117，正租户网络 Proposal/ApprovalEvent/revision0；a0v116 active触发器 enabled=`O`，Runtime Host仍关闭。

## 关键剩余风险

当前 `aos_runtime` 对 `aip_action_approval_event` 的 INSERT 权限为 true，表上非系统 trigger 数为0；内部预检无法据此证明 Event 由合法 OIDC checker 签发。它只证明记录与当前依赖一致，绝非 active 授权。Proposal 行锁可串行化现有 Store 的 decide/withdraw，但不能防直接 SQL 伪造历史事件；Receipt预读也不提供并发唯一性保证，未来受控写路径须在同事务依靠固定键/唯一约束。BG00cb 先审并封闭固定网络动作 ApprovalEvent 的 DB直写来源（兼容其他 ActionType），设计可核正式身份签发与撤销边界；再做原子消费/active DB门的独立安全迁移。当前无第二真实 checker，首链仍未完成。
