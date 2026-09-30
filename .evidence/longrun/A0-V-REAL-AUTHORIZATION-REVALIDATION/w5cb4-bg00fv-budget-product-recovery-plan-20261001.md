# BG00FV 私有预算签发客户端/产品原请求恢复

基线AOS-001036/3d63e469。复习231-5审批与unknown保留、公共契约exact refs/no token URL、429，以及network client/application/private transport、原budget product与PG测试。当前真库只读，m1单写，先计划后编码。

## 文件级计划
- aip_private_request_file.py：仅抽出原budget activation product O_EXCL/NOFOLLOW/0600/writeall/fsync(file+directory)原子创建小函数，FileExists返回False；不删除不重试、不含身份裁决。aip_budget_activation_product.py用该函数替换原写入块，原鉴权/envelope/_read/conflict/dispatch流程不变；累计老产品测试必须通过。
- aip_budget_cost_client.py：BudgetCostEndpoint固定绝对短socket与API/issuer/GID，复用private transport建立独立kernelpeer后一次发送execute_once或inquiry。64KiB，响应严格键集合/类型/状态/decision/hash/eligiblefalse/ref校验，未知/截断/失败返回unresolved且不重发；连接未完成稳定blocked。token仅在已验peer的内存帧内。
- aip_budget_cost_product.py：明确外部OIDC+当前成员鉴权复用原budget _authenticated；请求body仅proposalHash+decision或reason，route固定operation/proposalId，无客户端token/key/租户。slot=scope+actor+operation+proposalId，body不参与slot，防换body重开请求。0600私有envelope保存原body/hash/key/actor/ref，无JWT，<=4096；原子保存且fsync后最多一个execute_once，其后包括POST重复和GET刷新都只inquiry；重新获取freshJWT，不保存旧token。不信损坏/错actor/权限/FIFO/symlink或部分写，503且不删除。结果未定不能生成新key。
- 明确配置 AOS_BUDGET_COST_API_CONFIG 私有JSON只含schemaVersion/socketPath/apiUid/issuerUid/ipcGid/requestDirectory；复用私有读取器，禁止数据库字段/隐式默认。配置缺失503，不能回退旧preview signer或共享API直签。
- routers/aip_budgets.py新增POST/GET /cost-proposals/{proposal_id}/review-requests/{operation}，POST body决定/revoke，GET只safe refs；result状态200/202/409/503，正常响应no-store，权限失败不泄漏请求。UI未改，当前正式配置未部署，不当业务通过。
- test_budget_cost_client.py：实际socketpair帧/截断/响应漂移/单发送，以及真实kernel错误身份零发送；不是跨UID正式正向证明。
- test_budget_cost_product_pg.py：真实TLSJWT/PG当前成员、持久化/刷新/冲突/unknown/并发/损坏/private配置/HTTP只读恢复。若用transport适配到FU service明确为集成适配不证明独立OS部署；实际PG写由FU真实issuer factory完成。fsync故障仅测试磁盘，失败不派发。老预算product/networkclient累计回归。

## 交付与后续
RED缺模块→专项/累计/复审/verification，精确commit/Delivery/CAS/430/D-waves/Prime。不push、不动旧dirty/商城源/当前库/Host/Provider/旧Run/230L0。接下来FW产品审核UI与真实浏览器只读/禁入验收及受限consumer原子激活；正式OS身份与全链安全部署仍独立波。Goal完整目标保留，看护仍仅方案。

复审补充：旧budget product只将18行写入块替换为3行调用/碰撞回读，原state机不复制不重写。API持久slot只绑定scope/actor/operation/proposalId，改decision/hash/reason不能重开slot；任何一次持久化失败保留现场，后续不以缺Receipt为重发依据。测试transport适配只能证明产品→FU核心真实PG合同，不能替代正式不同OS UID部署。额外验证maker撤销刷新及身份错配零文件/零发送；正常结果不回传保存body/reason。

复审追加：FU execute_once内部已独立读回Receipt，client已验observed/hash/decision/eligible；产品应直接保留该observed，避免有限max_connections=1进程退出后第二次连接让成功退化unresolved。新增RED锁定首个成功只一帧；失败/未知仍只Inquiry，后续GET/POST重复保持原key。
