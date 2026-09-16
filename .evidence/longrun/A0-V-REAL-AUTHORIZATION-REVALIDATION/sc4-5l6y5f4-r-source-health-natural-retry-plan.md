# SC4-5L6Y5F4 R：数据源健康与自然重试方案

## 1. 目标与前态

- 前态提交固定为 `b85667a2`。P 波次在 `2026-09-17 00:00 +08:00` 由 Cron 自然产生一次运行，未读取任何业务行，终态为失败；计划随后已禁用，未产生 ingress、occurrence、Case 或 Run。
- Q 波次已经让正式管道保留安全、有限的 SSH/MySQL 错误码，但当前 18181 进程早于 Q 提交启动，不能把工作树代码视为已部署代码。
- 本波次先用保存的数据源配置执行独立目录级健康检查；只有连接健康、当前安装/权限窗口/策略/绑定均为精确后继且计划保持禁用时，才允许装备下一次 Cron 自然窗口。

## 2. 设计

1. `source_connection_probe.py` 继续只读取 `meta_source` 的租户内保存配置，并通过 `information_schema` 枚举已配置表；不读取商品、订单、客户等业务表数据。
2. 探针失败时复用 Q 波次的 `connector_failure_code`，对外仅返回白名单错误码；未知异常仍返回 `SOURCE_PROBE_FAILED`，不暴露主机、端口、用户名、密码或原始异常。
3. 探针错误分类先用单元测试覆盖 SSH 未就绪、MySQL 连接失败和未知敏感异常，再受控重载 18181，使 Q/R 代码进入实际服务。
4. 真实探针只执行一次；成功才进入后继授权。失败则记录安全错误码并停止本窗口，不重试业务读取。
5. 后继授权必须逐项引用 L v1 的 SourceSelection、PipelineControl、ScheduleBinding 与 Policy8 Receipt；生成新的精确有效期、Policy9 和当前 installation/generation 的 event-control binding。不得扩大 route，不得使用旧授权或投影状态替代 Receipt。
6. Cron 装备沿用 `0 * * * *`，只允许一次自然源调用，禁止人工 `POST /runs`。终态出现后立即禁用并回读；未知终态禁止重发。

## 3. 变更文件

- `services/aos-api/aos_api/source_connection_probe.py`：增加安全连接失败码透传。
- `services/aos-api/tests/test_source_connection_probe.py`：覆盖白名单分类及敏感信息不泄漏。
- `scripts/a0v_l_source_health.py`：固定租户、固定 source/revision、单次只读目录探针与私有证据。
- 后继窗口若健康放行，再新增独立 v2 profile；不改写 P 波次已经封存的 intent/result。

## 4. 退出条件与停止规则

- 代码退出：定向测试通过，Q/P 相关回归通过，AR2 closure 校验保持无新增错误。
- 运行退出：18181 重载后 `/v1/health`、`/v1/ready` 为 green；真实探针返回成功且无业务行载荷；或返回一个安全失败码并停止。
- 自然窗口退出：精确后继授权、策略和绑定全部回读一致后才装备；只观察一个自然 Cron 终态，随后禁用；租户 canary、inflight/unresolved 必须为零。
- 同阶段连续两次失败、终态不明、哈希/Receipt/租户/有效期任一不一致，立即停止该外部动作并转入只读诊断。

## 5. 风险与回滚

- 探针会建立 SSH/MySQL 连接并读取表目录名称，属于真实只读连接，不是业务数据更新。
- API 重载期间会有短暂本地不可用；独立 Runtime Host 不随 API 重启。
- 代码回滚仅移除安全分类分支和固定探针脚本；运行回滚是保持 schedule disabled，不删除历史 Receipt 和 P/Q 证据。

## 6. 运行中校正（2026-09-17 00:20 +08:00）

- Policy9 已成功写入。首次 Policy9 enable 命令错误沿用了 Policy8 的 binding revision 1，事务以 `event control binding revision conflict` 拒绝。
- 只读回查确认：Policy9 head 为 disabled、Policy9 无 binding、失败 idempotency 无 Receipt、schedule 仍 disabled；Policy8 在 Policy9 put 时已退役为 binding revision 2/disabled。
- 由此确认 CAS 粒度是 `(policyId, policyRevision)`，Policy9 首次 binding 的 expected revision 必须为 0，成功后 revision 为 1。
- 原失败 intent 不重发。纠正使用新的 v3 state、idempotency 和审批；第二自然观察器据此固定 Policy9 binding revision 1。
