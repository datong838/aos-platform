# s3o-w-ae 第一切片｜BI 有限发行进程接原服务及未知提交对账

## 依据与范围

- 231-3/231-9、D-wave s3o-w-ae、630 接续：独立 BI 登录的原 prepare/rebind/Receipt 已在隔离签名 full schema 正反；现有 `aip_bi_plan_issuer_process.py` 仅准入 listener，没有 accept/业务 dispatch。`aip_bi_plan_issuer_ipc.py` 已核内核 peer/有限帧/租户，`aip_bi_plan_issuer_service.py` 已有每请求 OIDC、持久 attempt、未知结果只读 Receipt 对账。
- 当前真实库只读、正式角色/外部 IdP/六 Agent 缺失，绝不以 test-only 签名或身份放行当前 HTTP/Host；本切片只在可销毁签名库证明实际 DB 服务组合与至多一次结果。

## 文件级施工

1. `services/aos-api/tests/aip/test_aip_bi_plan_issuer_process.py` 先 RED：现有进程缺少可信签名来源下的原服务/Reader 组装和有界 accept；错配置、错租户和预检失败不得建 socket；单连接只调用一次私有 IPC，超时结束。该测试的合成 peer 不计真实跨 UID 正向。
2. `services/aos-api/aos_api/aip_bi_plan_issuer_process.py` 只新增可信本地配置注入的原 `ApprovedBIPreparationResolver`、`ActiveBIBusinessResolver`、`SignedBIPlanPreparationService`、`SignedBIPlanActiveRebindService` 与原两 Reader 的同一独立 DB 工厂；复用 `bi_issuer_listener`、`serve_one_bi_issuer_connection`、`dispatch_bi_issuer_command` 的已有门及至多一次 marker。不得由客户端传 DB 路径、actor、签名根或权限。
3. `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 在现有 test-only 独立 BI 登录/真实签名安装下，原 rebind 提交后模拟回执链路断开，复用同键只读回原 Receipt，证明原服务实际只调用一次、Plan/Receipt 不重复；另核缺 Receipt unresolved 和改命令 conflict。OIDC 测试替身只限隔离测试，不作为正式身份验收。
4. 专项/相邻回归、编译与方案一致性复审、verification、m1 精确提交、AOS/Prime/D-wave。真实不同 UID、正式 role→scope+subject/IdP/六 Agent、当前库一致备份/全链克隆/零执行切换留独立门，Host/worker/Provider继续关闭。
