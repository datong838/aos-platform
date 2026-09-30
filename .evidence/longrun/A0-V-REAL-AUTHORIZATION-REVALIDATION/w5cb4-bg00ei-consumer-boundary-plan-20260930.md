# BG00EI｜网络原子消费者身份与回执边界

基线 m1@45ac8c3a / AOS-000997；复习231-1/231-3、BG00EE与EH。BG00EE要求非特权函数owner、窄caller、独立issuer。现有a0v118保护批准Event，a0v116禁止active INSERT；但普通runtime仍可插入operation=network_policy.activate的Receipt。此记录是下一原子消费者的幂等依据，必须在开放消费者前封住来源。

## 文件级施工

- 新增 `services/aos-api/alembic/versions/a0v_119_network_consumer_boundary.py`，只在隔离测试库升级。本波新增专用role与Receipt INSERT来源门，不修改旧migration，不开放active，不迁移当前实例。
- 新增 `services/aos-api/tests/aip/test_network_consumer_boundary_pg.py`：标准一次性PG，旧代码RED证明role缺失与runtime伪造activation Receipt成功；实现后验证role属性/双向membership为空、caller无法SET owner/runtime/issuer、runtime和issuer均不能伪造activation Receipt、普通publish Receipt仍可写后回滚、active INSERT仍失败。
- 新增对应verification，保留入口/失败命令与范围；随后D-waves、Delivery、authority/Prime及m1精确提交。

## 权限矩阵

| 身份 | 该波属性和权限 | 下一波最终职责 |
|---|---|---|
| aos_network_approval_issuer（已有） | 保持现有a0v118；不能创建activation Receipt | OIDC独立checker签发Event，不能消费 |
| aos_network_consumer_call | NOLOGIN/NOINHERIT/NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION/NOBYPASSRLS；无双向membership；不授表DML | 仅EXECUTE固定原子函数；凭据与受控服务启用另波 |
| aos_network_consumer_owner | 同上；没有登录、成员、表所有权；本波不授DML | 拥有一个固定search_path的SECURITY DEFINER函数及精确表/列权限，不能发行Event |

若同名role已存在且属性或任何membership不符，migration失败，不自动修正角色。Receipt来源门要求session_user为consumer_call且current_user为consumer_owner；caller没有SET owner资格，当前没有消费函数，故所有普通调用保持禁入。数据库超级管理员能改变角色/DDL，属于可信部署边界，不能声称数据库可对抗自身管理员。当前API超级用户路径不得作为consumer部署身份。

## 原子函数后续合同（BG00EJ，未在本波开放）

参数只接org/project/proposalId/approvalEventId；candidate与目标hash从已批准且不可变的Proposal/Draft读取，禁止调用者传入任意active payload。按Proposal→唯一Approval/撤回→当前maker/checker与元数据→Network head→Egress head/revision的统一顺序锁定；核hash/绑定/版本/当前角色/有效期/依赖，最终DB clock复验。函数owner仅获得所需表SELECT和锁所需的列UPDATE，以及Network head/revision/Receipt窄写权，配置独立租户RLS；不继承aos_runtime。

固定Receipt消费键=proposalId，requestHash绑定tenant/proposal/Event/target；原子写head/revision/Receipt。重入只返回原不可变Receipt，hash冲突拒绝；未知结果只读对账。完整函数正负/并发/回滚证明后才调整active gate为仅允许该函数身份路径。当前实例迁移与真实授权仍需独立备份、全链克隆、零执行窗口，不能以本波role存在声明首链可用。
