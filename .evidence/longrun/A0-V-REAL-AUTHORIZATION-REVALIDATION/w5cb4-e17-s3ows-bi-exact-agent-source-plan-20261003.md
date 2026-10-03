# s3o-w-s 第一切片｜BI 发行函数精确六 Agent 来源

## 方案复习

- 231-9 规定六数字同事是既有 AgentInstance 的引用，签名 BI 模板只包含角色槽，实例分配和审批另取当前权威。231-3 要求事务内持锁复核。D-wave s3o-w-s 要先收紧受限函数的可查询集合，再谈正式 migration/身份。
- s3o-w-r 的 test-only 函数可读取同租户任意六互异 active Agent 的 ID/version；原服务只传 `BI_ROLE_BLUEPRINTS` 六 ID，但数据库 EXECUTE 原语自身仍太宽。当前真实库没有该函数/发行登录；不能据此创建正式身份。

## 文件级清单

1. `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py`：先加第七个隔离 active Agent，将其混入六 ID 的直接函数调用，RED 应显示当前函数错误返回六行；再把函数约束改为与 `BI_ROLE_BLUEPRINTS` 的六个精确 ID 集合相等，顺序无关。错租户/缺重/冒用、并发停用、Plan/Receipt 与重放仍需通过。
2. 本切片不改生产 API，生产服务已固定传 `BI_ROLE_BLUEPRINTS`；运行相邻回归，核 test-only 对象零残留，并只读核当前卷。若需将身份/actor 绑定到正式函数，单独设计受信 OIDC 与凭据边界；`aos.actor` 之类可由登录自行设置的 GUC 不充当认证。

## 退出

- 原签名全 schema 与相邻回归 GREEN 后只记隔离函数表面收紧。正式 migration/ACL/凭据、当前库备份/克隆/零执行切换及正式六 Agent 来源继续独立施工，当前真实库只读，Host/worker/Provider关闭。
