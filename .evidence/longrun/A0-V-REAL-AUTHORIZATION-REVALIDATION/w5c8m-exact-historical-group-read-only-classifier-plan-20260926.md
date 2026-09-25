# W5c8m｜精确历史源组只读见证分类计划

## 上位/边界

承接 W5c8j/k/l、`a0v_045/097`、AOS-000674。sidecar 仍空且运行角色无写权限；W5c8k 纯见证只在隔离夹具通过。真实库未迁 `a0v_096/097`，真实 `aos-extension` profile 停止，原 Run 现状未知。本波不得“扫真实全库”；先只对**明确给定的单个 group UUID**在同一个 `REPEATABLE READ READ ONLY` 事务做状态分类，绝不自动 INSERT/ACK/source 调用。

## 文件级清单

- 复习 `pipeline_snapshot_group_locator.py`、`pipeline_snapshot_group_canonical_witness.py`、`a0v_045/097`、W5c8g 同快照限制；核 role/tenant/read-only 状态和无锁历史读取。
- 新增 `services/aos-api/aos_api/pipeline_snapshot_group_witness_classifier.py`：输入精确 `TenantScope`、UUID group 与**已开启只读事务**的连接；只读原 claim/input/member，不读 ecommerce source。返回枚举 `READY_CANDIDATE`/`MISSING_GROUP`/`MISSING_INPUT`/`HASH_DRIFT`/`MEMBER_DRIFT` 等，不返回原 JSON 或可执行授权；查询需上限 13 个成员，避免任意宽扫。
- 先新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8m_exact_group_classifier_pg.py`：隔离 PG RED→GREEN，真实保存组正例、错 UUID/租户、可写连接、缺 input/hash/member 负例；不可构造真实表篡改时用纯函数行集注入并注明覆盖层级，不把 mock 当 PG 正例。`dev-org` 只负例。
- 不新增迁移/受控 writer/ACK/Worker 入口，不读取真实历史行。未来批量扫描、真实只读扫描许可和回填审批另立计划；本波结果类型不能作为写权限。

## 01:48 CST 收敛：保留 sidecar SELECT 停线

W5c8l 明确只建立空表且不给运行角色任何表权限。若本波为了分类 `SIDECAR_CONFLICT` 临时授 SELECT，会改变该安全边界；而该判断并非验证原 claim/input/member 必需。故本波不查询 sidecar、不授运行角色 SELECT，返回值仅表示原历史组**候选**。sidecar 与原 input manifest hash 的精确对照移交未来受控 writer/独立权限方案，不拿缺少的状态伪装已测。

## 九步

1. 复习上位方案/产品边界、m1/Git/authority/专用 PG。
2. 本文件先提交。
3. 先 RED：缺模块/错误状态必须 fail-closed。
4. 最小只读分类实现；无法证明 role、只读和 boundedness 则 STOP。
5. 专项/累计、测试库 0、静态检查。
6. 浏览器仅只读记录；真实目录不可用则不可验收。
7. 方案/代码一致性复审，区别 READY_CANDIDATE 与回填授权。
8. verification/m1 提交、D-waves/AOS CAS/Prime 回读。
9. 自动下一波 W5c8n：先设计有界多组扫描与拒绝式报告，然后评估受控 writer，仍不自动应用真实库。

230 L0 挂起、商城源不读、unknown 不重发/不手工 `run_definition`；m1 单写不 push、不动其他分支。
