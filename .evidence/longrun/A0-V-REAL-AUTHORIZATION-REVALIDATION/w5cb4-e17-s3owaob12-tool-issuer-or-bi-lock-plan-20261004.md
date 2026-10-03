# E17-s3o-w-ao-b12｜Tool 正式发行来源门与 BI 安装锁接续计划

## 上位方案与当前证据

- 231 四层/签名安装及 BIND-1 31 要求 exact 来源、租户/权限/CAS/Receipt。b6 两条 strict xfail 是无 ToolDefinition 前打开普通 writer、写 ToolBinding 却无同事务 RegistryReceipt；b8 当前原卷 ACL 证明 runtime 可 INSERT/UPDATE ToolBinding、可 INSERT 共享 Receipt。四份当前 signed bundle 无 ToolDefinition，正式 issuer/Owner/安装 epoch 来源不齐。不得伪造当前 Tool 正向或只加应用层 Receipt。
- 回读 s3o-w-p 至 s3o-w-ad：BI 安装锁已接原 `SignedBIPlanPreparationService` 三入口，并继续走独立受限登录的签名来源/受控权限/Agent 及 active rebind 隔离验证；本波不重复 s3o-w-o 的备用步骤。当前库仍无正式角色/函数/凭据，迁移与切换另波。

## 文件级步骤与退出门

1. 只读核 `aip_assignee_resolution.py`、`aip_assignee_resolution_store.py`、`aip_registry_issuer_connection.py`、ToolBinding/Receipt migration 和四签名 manifest 的精确来源。输出缺口矩阵：signed source、专用 issuer、同事务 Receipt、runtime 收权、禁旧入口。公共 Tool 发行协议若未冻结，不进行生产 DTO/ACL/路由改动；保留 b6 strict xfail。
2. 在独立 test-only PG 原 ToolBinding/RegistryReceipt 表上，以非 owner、NOINHERIT Tool issuer 与 runtime 登录验证 **DB operation/session 分流**：runtime 可继续发行已有合法非 Tool Receipt，但不能插入 `tool_binding.upsert`；Tool issuer 只能插 Tool 专用 operation，须同事务找到精确 ToolBinding 版本/租户且受幂等键约束。先写会失败的目标验证，再最小隔离 SQL 协议；无正式 ToolDefinition 时不调用原 active Store 制造正向。
3. 专项/相邻回归、错租户/错误版本/无配对/重复键/故障回滚、一次性角色/函数/触发器/库残留清理，复审代码与上位方案；生产代码变更才需重启原卷和浏览器。当前原库只读，Host/worker/Provider关，不造外部效果。

## 本波停止条件

本波隔离 SQL 只证明发行身份与 Receipt 防伪能否实现，不等于正式 Tool 正向；正式 signed source/Owner/epoch 缺口仍留门控。若该公共协议需实质裁决，转 D-wave 其它已登记安全切片，不把局部缺口扩为 Goal blocked。org-org/dev-project 唯一正向，dev-org 零副作用；不读商城源、不重放旧12 Run、不手工 Run、不碰230 L0、不 push。
