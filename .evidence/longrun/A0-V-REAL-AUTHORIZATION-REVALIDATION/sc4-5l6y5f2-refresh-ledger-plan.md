# Y5f-F2 接续回执存储

2026-09-16，m1 21f4564e，唯一迁移写者。当前主库066；本波仅隔离库应用新迁移。

文件：新增 services/aos-api/alembic/versions/a0v_067_dispatch_configuration_refresh.py、aos_api/ecommerce_dispatch_configuration_receipt.py、tests/test_ecommerce_dispatch_configuration_receipt.py、tests/extension_runtime/test_dispatch_configuration_refresh_schema_pg.py。

新表extension_dispatch_configuration_refresh_receipt：双租户、group、revision链、receipt UUID、root activation operation/resume receipt、installation/generation、actor、request/request_hash、body/content_hash、created_at，组内key唯一与prev receipt/hash FK。root activation和resume分别FK既有表；每次refresh保留同root，原resume历史不改。body规范固定为schemaVersion/receiptId/revision/activationOperationId/activationResumeReceiptId/actor/request/requestHash/createdAt，request为F1严格wire。decoder重验所有列投影/请求hash/内容hash、前驱Ref/原始时刻、scope/安装/group不漂移。

数据库RLS ENABLE+FORCE，双scope policy；原history mutation trigger拒绝UPDATE/DELETE/TRUNCATE；runtime和maintainer仅SELECT，PUBLIC无权。本波不给应用角色INSERT或执行函数权限，不存在生产写入口。FK、唯一性、请求JSON形状与大小/版本类型、prev链和hash由DB约束及后续Owner共同守护。row级trigger需校验body/column projection并将prev绑定同scope/group/root/安装代次，以及原root resume phase。真正configure/enable/current policy/审批/原子dispatch更新在F3受保护函数里完成，不以存储记录本身代表已执行。

验证：严格codec正反例；原完整迁移bootstrap隔离PG验证表权限、租户策略、不可变拒绝、缺失root拒绝。当前波次没有正向原子refresh执行验收（F3），不声称真实接续通过。主库067部署须F3/F4完整接续与disable演练后进行；禁止数据库owner写入正式业务回执作为替代。

## 完成证据

- 隔离 PostgreSQL 的迁移、RLS、双租户不可见、应用角色拒写、历史不可变、根回执约束和连续链约束：18 项通过。
- codec、F1 请求合同、既有 cutover action binding 与 package registration 回归合计：累计 64 项通过（`/tmp/aos-y5f2-cumulative.log`）。
- 先以 `sourceRuntimeRevision` 回退一版并重新计算全部哈希，隔离库如期拒绝；随后增加“后继 source 必须等于前驱 target”的数据库约束并转绿（红灯记录：`/tmp/aos-y5f2-chain-red.log`）。
- 主库留痕 `y5f2-main-unchanged.json`：迁移仍为 `a0v_066`，新回执表不存在，业务 Run/Claim 数量未变，启用 Schedule 为 0。
- `git diff --check` 通过；本波未增加写权限、未提供生产写入口、未发布策略、未恢复业务 Run。

## 与方案的一致性及风险

F2 只落“可验证的接续历史容器”，与 F1 的严格 wire/hash 合同一致；数据库同时校验原始 resume 根、同租户/同组/同安装代次和逐版连续性。现存缺口是 F3 原子 Owner 尚未实现，因此任何数据库 owner 手工插入都不是系统执行证据，067 也不得单独部署到主库。下一波 F3 将先补方案，再实现受保护的单事务 Owner，并把当前权限、审批、configure/enable 终态、当前 dispatch CAS 与回执写入合并为一个原子动作。
