# BG00FF 原创建请求持久恢复方案

基线m1@69bcef83 / AOS-001020；复习231-5§3/5/7、公共产品契约、413、BG00FD/FE。

## 查明缺口与顺序
现有RuntimeNetworkPolicyPreviewPanel只有只读预览；BG00FD查询须原candidate/expiry/key，刷新无持久引用不能安全创建。本波先补创建产品后端必要合同，再由BG00FG接原表单；首链范围不缩减，正式OS/OIDC、部署、配置和自然消费仍独立待验收。

## 文件与合同
- 新aos_api/aip_network_proposal_product.py：用API现有IssuerApplicationConfig私有attempt_directory承载独立proposal-product-v1命名空间，不使用issuer进程密钥；外部OIDC每次重新验证。目录非审批权威，PG仍唯一提案事实源。
- 稳定槽按scope/actor/policyId/candidateRevision/expectedHeadVersion生成，不含可变candidate/expiry。先验证输入与总字节上限4096；O_EXCL独占写完整原body/hash及身份，0600、文件和目录fsync成功后才调用原producer一次。并发/刷新/再次POST已有槽只调用BG00FD查询；不同body409。
- GET按policyId/revision/headVersion恢复原body（不返token），仅查询原PG请求；缺槽not_attempted仅当前slot未占。损坏/symlink/FIFO/权限错503，不能作为缺槽。原输入在有效期后仍可查询历史。
- 修改router：POST/GET /networks/proposal-intent，复用现有API配置依赖与错误映射；原接口不变。无DDL/迁移/真实实例启动。
- 新tests/aip/test_network_proposal_product_pg.py：真实隔离PG producer+查询、TLSJWT、响应丢失、并发独占、重载、跨身份/损坏/不同输入。故障注入只证明故障合同，不作正式业务证据。

## 风险、限制、验收
持久槽出现后即视为可能尝试；进程在落槽后调用前崩溃也不自动重发。原PG查询仍unresolved时保留，不能通过更换key/时间绕过；无副作用确认后的正式恢复产品项留后续，不能将此路径称完整恢复通过。文件不可丢失、不可切临时目录；正式部署需绑定备份恢复及唯一写者。
专项RED→最小实现→相邻回归→复审→verification→m1精确提交/Receipt/CAS/414/D-waves。无UI修改，本波不宣称浏览器或真实首链通过。当前真实库只读、不push、不读商城源、不手工Run、不回放旧12Run、230 L0挂起。

复审补充：GET仅在服务端恢复原body并查询PG，响应不披露原body/token。新增fsync失败禁止dispatch且保留槽、创建前失败不自动重发两类用例。代码的持久记录是防重发事实，不授予新提交/批准/消费权限；实例材料与原请求无副作用裁决未补齐前仍pending。
