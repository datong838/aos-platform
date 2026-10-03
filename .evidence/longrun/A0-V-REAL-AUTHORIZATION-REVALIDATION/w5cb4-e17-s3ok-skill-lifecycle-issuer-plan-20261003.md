# W5CB4 E17-s3o-k｜原 SkillBinding evaluate/update 发行权限计划

依据 231 总控/231-4/231-9、582 与 D-waves s3oj 下一波。当前真实库只读、Host/worker/Provider 关闭；只在 disposable PG 验证原命令。此切片验证失败关闭的 readiness 与 provisioning→revoked 生命周期，不用 test-only Published Skill 证明正式 active 配置。

## 文件级判断

- 原 `AipSkillRegistry.evaluate_binding` 在写前调用真实 `AipSkillBindingReadinessService`，其 published 检查还读取 `aip_publication_event`；当测试夹具无正式事件/route/gate 时必须是 blocked。评测随后对 `aip_skill_binding` 做 expected_version CAS UPDATE，写同事务 `RegistryReceipt`；同键 replay 只回读。原 `update_binding` 对 revoked 无 readiness 放行，仍需 expected_version/from_status CAS UPDATE 与 Receipt。
- `aos_aip_skill_issuer` 延续 create 的 SkillBinding SI，本波增 UPDATE、不增 DELETE；补 `aip_publication_event` SELECT，不给任意其余表写。连接准入检查 SkillBinding SIU、CapabilityBinding 和 PublicationEvent SELECT 且 FORCE RLS，Agent 登录与原 Agent 路径保持旧 ACL。隔离库普通 runtime Registry Receipt INSERT 持续撤销。
- 原命令 RED 还揭示：可选 route/policy/gate 为 `None` 时 `_json(None)` 变成 JSONB `null`，不等于 SQL NULL，违反三个 `*_ref_chk`。`evaluate_binding` 本应能把来源不足保存为 blocked。只在原 SQL 三个可选引用参数上把 Python `None` 直接交给 `%s::jsonb`，其余非空引用仍沿用原 JSON 序列化；补单独最小修复任务的文件归属。
- active 的正向需要正式持久化发布/路由/预算/审批及现时有效证据，本波不伪造这些 authority。这个实例级门继续 pending。

## RED → 最小实现 → 验证

1. 在 `services/aos-api/tests/aip/test_e17_s3oj_skill_issuer_pg.py` 增原 create 后 evaluate(真实 readiness)/update(revoked) 测试；在旧 Skill issuer ACL 下应因发布事件 SELECT 或 UPDATE 不足而失败且版本/Receipt 不发生半提交。夹具仅 test-only。
2. 修改 `services/aos-api/aos_api/aip_registry_issuer_connection.py` 的 Skill 命令族预检；测试 fixture 精确增加 PublicationEvent SELECT 与 SkillBinding UPDATE。另在 `services/aos-api/aos_api/aip_skill_registry.py` 最小修复可选引用 NULL，保持非空引用编码不变。覆盖 blocked readiness、create/evaluate/update/replay、错误 expected_version/同键异载荷、无 PublicationEvent 读权/非法 DELETE、跨租户。
3. 运行 s3oj/s3oi 原路径与 Skill 发布相邻测试，静态/差异审查；签名预检/备份 SHA/当前库版本回读后只局部重载 API，记录 Host 禁入。无 UI 变更不重做浏览器动作。
4. verification、m1 精确提交、AOS/Prime/01/06、D-waves 和下一波清单。若真实 readiness 读路径还有未盘到的表权，先记录具体拒绝再修订本方案，不能授通配读写。

回滚是撤本波未正式接线的连接预检增量；不修改当前库/卷或已批准安装。
