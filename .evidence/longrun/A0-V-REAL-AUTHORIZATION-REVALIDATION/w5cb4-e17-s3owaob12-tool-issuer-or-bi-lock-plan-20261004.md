# E17-s3o-w-ao-b12｜Tool 正式发行来源门与 BI 安装锁接续计划

## 上位方案与当前证据

- 231 四层/签名安装及 BIND-1 31 要求 exact 来源、租户/权限/CAS/Receipt。b6 两条 strict xfail 是无 ToolDefinition 前打开普通 writer、写 ToolBinding 却无同事务 RegistryReceipt；b8 当前原卷 ACL 证明 runtime 可 INSERT/UPDATE ToolBinding、可 INSERT 共享 Receipt。四份当前 signed bundle 无 ToolDefinition，正式 issuer/Owner/安装 epoch 来源不齐。不得伪造当前 Tool 正向或只加应用层 Receipt。
- s3o-w-o 已在隔离 PG 证明只读 BI issuer 对安装行直接 `FOR SHARE`/UPDATE 被拒，专用 SECURITY DEFINER 安装锁函数可在不授安装 UPDATE 下持有 CAS 锁；尚未接原 `SignedBIPlanPreparationService` 完整事务。

## 文件级步骤与退出门

1. 只读核 `aip_assignee_resolution.py`、`aip_assignee_resolution_store.py`、`aip_registry_issuer_connection.py`、ToolBinding/Receipt migration 和四签名 manifest 的精确来源。输出缺口矩阵：signed source、专用 issuer、同事务 Receipt、runtime 收权、禁旧入口。公共 Tool 发行协议若未冻结，不进行生产 DTO/ACL/路由改动；保留 b6 strict xfail。
2. 转不依赖正式 ToolDefinition 的 BI 锁切片：读 s3o-w-o 隔离 SQL 方案、原 `SignedBIPlanPreparationService` 安装锁调用与原签名 Growth1.13 full-schema 测试，确认函数可同事务保留 ETag/租户/安装 epoch、非 owner/NOINHERIT 身份和原 Store 不切成 runtime。先在独立 test-only PG 真实原调用 RED，再最小测试/协议修复；不得给 issuer 安装表宽 UPDATE。
3. 专项/相邻回归、异常回滚/CAS/错租户/超时、独立库残留清理，复审代码与上位方案；生产代码变更才需重启原卷和浏览器。当前原库只读，Host/worker/Provider关，不造外部效果。

## 本波停止条件

若 Tool 正向缺正式签名来源，则只封存缺口并推进 BI 隔离链；若 BI 原调用发现公共协议需用户裁决，再从 D-wave 其它已登记安全切片选路。不得把局部缺口扩为 Goal blocked。org-org/dev-project 唯一正向，dev-org 零副作用；不读商城源、不重放旧12 Run、不手工 Run、不碰230 L0、不 push。
