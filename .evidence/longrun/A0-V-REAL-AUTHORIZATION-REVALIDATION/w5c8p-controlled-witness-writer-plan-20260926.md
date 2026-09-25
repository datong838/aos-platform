# W5c8p｜历史 canonical 见证受控写入设计与隔离验证计划

## 上位边界

承接 W5c8l 空不可变 sidecar、W5c8m 单组分类、W5c8n/o 同快照有界报告和 AOS-000677。W5c8o 的第二/第三组是 synthetic 缺输入负例，不提供回填授权。`a0v_097` 目前只把 request hash FK 到原 claim，manifest hash 未 FK 到原 input；表所有者仍能首次插入自洽但不匹配原输入的见证。本波只在隔离 PG 完成受控 writer 的方案/最小实现/拒绝测试，**不迁真实库、不扫描真实历史、不运行真实 writer、不建 ACK**。

## 文件级清单与先决复习

- 复习 `a0v_045/097`、W5c8l 权限审计、`pipeline_snapshot_group_canonical_witness.py`、分类/分页模块和不可变 Receipt/Host fence 上位方案；核对真实 profile 仍停止、m1 无别人改动。
- 先做权限决策 audit：受控 writer 必须是单独、默认无登录/无 runtime 授权的角色或精确 `SECURITY DEFINER` 路径；禁止 runtime、directory、maintainer 和 PUBLIC 直接 INSERT/EXECUTE。不得把现有表所有者能力表述为不可写。
- 如权限和原输入绑定可在隔离 PG 完整证明，新增最窄 migration/服务端函数：以精确双租户键+group UUID+双 canonical 文本为输入；单事务锁定原 claim/input/member，核对存储双 hash、JSONB 等值、成员完整性及 actor/tenant；显式拒绝缺输入、hash 漂移、并发/重复不同值、跨租户及错误角色。首次成功只能 INSERT 一行不可变 sidecar；同值重试最多返回已存在，不给 ACK/执行权。
- RED/GREEN 隔离 PG 测试先覆盖无写权限、合法原保存组、缺输入、hash 不匹配、JSONB 文本等值、跨租户、并发冲突/重试；用一次性 `aos_test_*`，不放松原触发器/RLS。若证据缺一项，仅交付设计审计与停止文件，不写半成品授权函数。

## 九步

1. 复习上位方案/产品、权限与当前 HEAD/测试环境。
2. 本文件提交，细化函数签名、角色及文件路径后再编码。
3. 先 RED 隔离 PG 权限与原输入绑定负例。
4. 最小迁移/函数，不接 Worker/ACK。
5. 专项、累计、静态、测试库 0。
6. 浏览器只读；无业务 UI 明示不可验收。
7. 方案/代码权限与 race 复审。
8. verification/m1/D-waves/AOS CAS/Prime。
9. 自动下一波 W5c8q：只读部署前门与真实 profile 恢复顺序方案，真实迁移/扫描/回填仍需独立明确证据门。

任何未知提交边界冻结，绝不重发或手工 `run_definition`；230 L0 挂起、商城源不读、dev-org 零 canary、m1 单写不 push。

## 第 3 步权限审计后收窄（2026-09-26）

核对 `a0v_097` 后确认表 owner 可直接 INSERT，旧表 RLS 虽 FORCE 但不能代替专用写主体；现有 `a0v_037` 提供 NOLOGIN/NOBYPASSRLS 专用角色样例。将本波退出条件收窄为**设计审计与零新增 EXECUTE**：先明确专用角色 owner、迁移时 role-membership 校验、原表 SELECT/sidecar INSERT 的最小授权、函数所有权与执行授权、RLS/搜索路径及回滚限制。未完成独立隔离 PG 角色/并发/原输入绑定红绿测试之前不得增加 migration 或 Writer。后继 W5c8q 承接编码与测试；原第 9 步的真实部署前门顺延后续波。
