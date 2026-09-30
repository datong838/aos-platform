# BG00FU 预算签发 schema 准入与独立 IPC

基线AOS-001035/0b0586d4。复习231-5 §5/6/7、公共产品契约、FS/FT和428，network issuer process/IPC/attempt/service、private listener。单写m1，当前真实库只读。正式OS/凭据部署仍独立安全波。

## 文件级计划
1. aip_budget_cost_preflight.py + aip_budget_cost_schema.json：只读pg_catalog采集a0v124/125五表的列/类型/default/约束/索引/RLS/策略/触发器、两guard函数正文与安全属性/权限，和reviewed manifest精确比对；检查runtime非高权及public schema无runtime CREATE。manifest只由本次隔离测试库迁移结果生成、人工核对与漂移负测，生产禁止采纳现场新基线。规范化owner OID为owner占位，但表/函数owner必须精确为平台迁移角色aos_app；列级ACL和有效权限纳入。数据库版本号不能替代这些证据。稳定拒绝码不回传SQL/密码。代码差异或PG deparse格式漂移可拒绝，需后续重新评审，不自动放宽。
2. aip_budget_cost_process.py：固定FT连接工厂与TenantScope，每事务执行schema门。frozen进程配置校验distinct API/issuer OS UID、当前UID/GID、绝对socket/attempt/credential、有限accept/timeout。复用owned_private_listener、open_private_issuer_listener/read_issuer_frame/require_issuer_peer，不重写peer或文件原子状态机。startup先OIDC/privatepath+read-only DB preflight，再打开socket。
3. wire严格schemaVersion整数1、method execute_once/inquiry、payload BudgetCostIssuerCommand，64KiB帧限制、拒绝重复JSON键/NaN/额外字段；token只内存、不得响应/文件。scope不符或peer不符直接拒绝。
4. service认证后先当前actor membership/read-only及schema核验；复用AttemptReceipt/_reserve_attempt_receipt namespace预算域+actor+operation（hash生成），key保持原请求。O_EXCL+fsync成功才一次execute；既存相同标记只inquire，冲突拒绝；unknown绝不再次execute。结果仅observed/unresolved/conflict和不可变预算结果/eligiblefalse；错误统一稳定码。保存hash不保存JWT/body，产品原请求body恢复后继完成。
5. test_budget_cost_preflight_pg.py：隔离迁移真实PG目录读、baseline核对，禁用trigger、替换guard正文、RLS/策略/约束/列级ACL漂移均拒绝并回滚fixture改动。实际工厂realTLS JWT+durable尝试，证明二次请求不再写、异常unknown不重发、原请求Inquiry回读。
6. test_budget_cost_process.py：实际Unix监听生命周期/内核wrong UID拒绝；协议格式/大小/scope；正式跨UID正向环境缺失不得伪造证明。纯单元适配测试若需替身必须明确标注，不充正式产品验收。无HTTP/UI改动浏览器不适用。

## 验证与交付
RED缺模块→专项与FT/FS/FR/网络IPC/attempt累计；compileall/diff/head125。不新增迁移、不触当前库/商城源/旧12Run/手工Run/230L0，不启Host/Provider。verification、精确commit、Delivery/CAS/429/D-waves/Prime。后继FV产品持久原请求恢复与私有客户端，之后受限consumer原子激活；当前正式部署和首链仍未完成。

复审补充：真实负例证明只归一化owner会漏过函数所有权转移；固定aos_app Owner并重新负测。macOS Unix socket路径按字节上限103预检，fixture使用本次专属短临时路径，不能用放宽监听权限修复路径过长。manifest由隔离迁移库生成且核对正文；SHA256 bab6a10a859b4d9cd04b15aec666c6fa47043ba844808950f850029377148f1f；来源a0v124 1d0dbbe412fe0acd94cff532cff12ccdfcaffe897eb599bad83979e585ea04e9，a0v125 41fe7212469620dc251a0c543c1ebcde06d108f2f40d269106842569f6b94e26。

复审确认：runtime不得再获其他角色成员资格；新增真实GRANT负例。临时socket目录继承/tmp的GID不符曾被门禁正确拒绝，fixture显式设置自身组后复验；未放宽production权限。正式实例仍须零DDL窗口，catalog预检不宣称能对抗受信迁移Owner在事务期间恶意改DDL。schema manifest已由现有package-data *.json纳入部署包。
