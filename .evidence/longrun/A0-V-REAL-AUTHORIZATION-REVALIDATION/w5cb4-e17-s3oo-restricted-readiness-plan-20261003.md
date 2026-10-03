# W5CB4 E17-s3o-o｜Capability readiness 受限读取身份与原评测

日期 2026-10-03。先复习 231 长程路线的租户/最小权限及首链真实证据、584～587 和 D-waves。s3o-m 实测原 evaluate 的默认 readiness 使用 `aos_app` owner；s3o-n 已令自定义发行连接缺显式 reader 时失败关闭。本波只在自动销毁 PG135 复现并修正受限路径，当前真库只读，Host/worker/Provider仍关闭。

## 权威与最小权限

- `aip_capability_revision` 是全局无租户的 catalog，无 RLS；scope-less 读取需要独立非 owner、无写权的登录。其余 `PostgresBindingDependencyAuthority` 查询 `aip_release_gate_decision`、`aip_eval_contract_revision`、`aip_evidence_bundle_revision`、`aip_eval_dataset_revision` 均按 TenantScope 读，现有 RLS+FORCE。
- `AipModelRuntimeStore`/Resolver 读 route head/revision、runtime policy、registered model、price、provider、provider health；有效模型还核 Eval Gate、runtime guard、quota/budget policy head/revision 与 BudgetRevision head/revision。NetworkPolicy 在 publish 路径，本次 readiness resolve 不调用，不授该表。只授予这些可达 SELECT 表，均需 tenant GUC、RLS+FORCE。连接固定 127.0.0.1/::1、数据库名、私有 0700 目录/0600 passfile，禁止 PG 环境捷径；校验 session/current_user、非 owner/非 BYPASSRLS/非 runtime、search_path/超时、read_only 与表权。无 scope 时租户表 RLS 应返回零行。不得借用写者登录或预览 owner。
- `AipCapabilityBindingService` 仍以显式 `readiness_service` 注入；构造 `PostgresBindingDependencyAuthority(reader)` 和 `AipModelRuntimeStore(reader)`，Resolver 同源。默认本机预览路径保持，正式路由切换当前库另波。Capability writer 的 UPDATE 仅对既有 Binding 原事务需要；保留原 create-only `capability` ACL 门，新增明确选择的 `capability_lifecycle` 门（同一独立登录但要求 UPDATE），无 DELETE/Receipt UPDATE/跨域写，不能把 test-only Capability/secretRef 当正式来源。

## 文件级顺序

1. 新增 `services/aos-api/tests/aip/test_e17_s3oo_capability_reader_pg.py`：先 RED 证明原评测无合法 reader、独立 read-only 登录无法接线；用原 SQL、真实 session_user/current_user、真实隔离 PG，不 mock readiness。测试 include catalog无scope/tenant scope、跨租户不可见、写权/角色/私有凭据/超时负例、原 create→blocked evaluate→replay/CAS/Receipt。缺正式依赖只能 blocked。
2. 新增 `services/aos-api/aos_api/aip_binding_readiness_reader_connection.py`，仅实现上述受限只读连接合同；最小改 `aip_registry_issuer_connection.py` 的 Capability UPDATE 门和隔离 fixture，`AipCapabilityBindingService` 继续显式注入，不追加隐式 owner fallback。
3. 专项及 Agent/Skill/Capability 发行相邻回归、`py_compile`、`git diff --check`；必要时只复验本机 API/Web 健康，代码经完整重启后是否已经加载单独声明。verification 精确记录 RED/正反与残余风险，m1 只 add 本波文件。

本波完成不等于当前库 ACL/OIDC 切换、正式 Capability active、八配置/Host/首链。当前卷若要迁移，另波先新全备、ACL-faithful 克隆、零执行窗口。
