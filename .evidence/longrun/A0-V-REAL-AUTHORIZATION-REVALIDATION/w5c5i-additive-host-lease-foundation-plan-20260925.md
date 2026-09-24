# W5c5i additive Host 租约基础与隔离 PG 合同方案（2026-09-25）

上位 W5c5h 排他设计、AR1-c `ar1_003` 受管目录、231 A0-V/231-9 BG-00。当前 Alembic head=`a0v_092`；本波接续 `a0v_093`，只增空表/受限函数，不接入启动器或 worker，不迁移生产数据，不重启服务。

## 文件级九步

1. 复习 `ar1_003` 身份/assignment/OID、`a0v_092` 迁移头、现有 PG 隔离夹具与 W5c5h 未实现风险边界。
2. 文件清单：本方案；新增 `services/aos-api/alembic/versions/a0v_093_host_lease_foundation.py`；新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c5i_host_lease_pg.py`；本 verification。Host/Owner Python 和前端零改。
3. Additive 空租约头与 append-only 事件表；`(org,project)` 唯一、DB 时钟 TTL、单调 epoch、token 摘要、当前受管角色 OID/Host/assignment revision 绑定。SECURITY DEFINER acquire/renew/release 限非特权且具目录成员资格的精确 session_user；直接表写权限全部撤销，函数只授目录角色；参数租户须与当前作用域一致；短有界 TTL。第二 Host 在未过期时拒绝，过期接管递增 epoch，旧 token/epoch 不得续租/释放；assignment/role 漂移冻结。无默认持有者或自动启动。
4. 隔离 PG 测试：空默认、同/异 Host 争用、并发只有一赢家、过期接管与旧 epoch 拒绝、角色/OID/assignment/作用域漂移、直接表写拒绝、历史不可改；不得用共享业务库。
5. 有界迁移/Host 相关与 W5c3–W5c5i 累计回归，隔离 PG 停用。
6. 浏览器只读验收 A0-V 整组仍停用；新表不应改变页面。
7. 复审：本波仅租约基础，现有 Host 不持有，workers 不 fencing；不能将租约空表视为“全机 0”或真实关闭授权。旧代仍须严格 24h 和单独方案。未知结果冻结。
8. verification 落盘提交，再 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆、读回。
9. 下一波 W5c5j：Host opt-in 与失权停止测试，默认 off；之后逐 worker fencing，未全覆盖前不能放行。

m1 单写不 push；商城源行不读；旧 attempt 不补跑；230 L0 挂起；dev-org 零 canary。
