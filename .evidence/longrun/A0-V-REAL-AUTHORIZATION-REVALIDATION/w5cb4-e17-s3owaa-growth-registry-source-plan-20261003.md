# s3o-w-aa 第一切片｜独立 BI 登录的精确 Growth 签名候选

## 上位方案与已知 RED

- 231-3/231-9、D-wave/624 要求原安装/签名来源、真实 AgentInstance 与独立受限身份，不允许表 owner/runtime 捷径。原 `ApprovedBIPreparationResolver` 在受限 BI 登录下失败；一次性签名库已证该角色对四张全局 Registry 表 SELECT 全为 false，不能为过测直接给宽表权限。
- 此切片在一次性 Growth1.13 全 schema 库验证**固定数据库受控函数**返回精确栖月汇已批准安装的 Growth 候选；仍由原 RegistrySnapshotReader/ReleasePolicy 和原 resolver 核签名、内容 hash、composition lock。正式当前库函数/ACL 迁移、角色到 tenant 映射、UID/OIDC、六 Agent 和首链另门；当前库只读。

## 文件级施工

1. `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py` RED：同一 test-only 非 owner/NOINHERIT BI 登录，原 resolver 带受限标志必须从 `None` 转为精确签名 selection；错 tenant/未批准安装/失凭据或撤 EXECUTE 拒绝；四张全局表 SELECT 始终 false。先期待正向、记录失败，再建 test-only function，不用生产库 DDL。
2. `services/aos-api/aos_api/asset_registry/registry_snapshot.py`：只新增显式受限 Growth 来源开关；已有 prepared read-only 事务时改从固定 `public.aos_bi_growth_registry_a0v_137(org,project,'snapshot')` 的 JSONB payload 读候选，再走原解析与 ReleasePolicy。默认全量 SQL 不变。拒非精确 scope、未准备事务、错 payload 形状；禁止客户端传 SQL 或函数名。
3. `services/aos-api/aos_api/aip_responsibility_template_authority.py`：仅当构造时显式限定一个 `TenantScope`，`_approved_rows` 改读同一固定函数的 `'approved'` payload；其它 scope 返回空。原 signed local mirror、trust root、snapshot matching 原样保留。
4. 一次性测试库中的函数由维护 owner 创建，固定 `search_path=pg_catalog`，验证 `session_user=aos_bi_plan_issuer`、请求 org/project 与事务 GUC，且第一切片仅 `org-org/dev-project`；只返回安装上已批准的 `solution.ecommerce.growth/1.13.0` 精确行/快照，`PUBLIC` 收权、仅 BI 登录 EXECUTE。函数必须校验当前安装、bundle/status/artifact/ref，不把其它 bundle 或 tenant 交给调用者。正式迁移要另补 role→scope 持久映射，不能将 test-only 硬编码直接搬到当前库。
5. 专项、相邻 Registry/Resolver、签名 full schema 正反、编译与方案复审、verification、m1 精确提交、D-wave/625/Authority/Prime。

## 下一门

此切片只证明隔离库的签名候选窄读取；需要再把同一受限连接注入原 prepare/rebind/Receipt Reader 和有限进程，做并发/撤权/未知提交恢复与真实不同 UID；当前正式实例另需一致备份、克隆全链、迁移 ACL、合法 IdP/六 Agent 与零执行窗口。不读商城源、不重放旧12 Run、不手工 run_definition、不碰230 L0、不 push。
