# s3o-w-ad 第一切片｜同一独立 BI 登录的 active rebind

## 上位依据与边界

- 231、D-wave s3o-w-ad、628 接续：先在可销毁签名全 schema 库证明原 `SignedBIPlanActiveRebindService` 和原 Receipt Reader，不能以锁函数单项通过冒充完整发行。
- 当前真实库只读；本波不迁移当前卷、不启 Host/worker/Provider、不接正式 HTTP；测试角色、固定函数、签名本地树只存在于隔离库。原 owner 路径不得改变。
- 受限登录应从批准安装的原 prepare 持续到原安装激活之后；prepared Plan 与 owner Plan 分开，避免原 owner 回归的版本竞争。Receipt 守卫仅限制独立 issuer，不能阻断同库合法安装生命周期。

## 文件级计划与 RED

1. `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py`：把已有隔离 issuer、私有 passfile、最小 ACL/函数按可控生命周期留到 active 阶段；异常或测试结束严格撤销角色、函数、策略和凭据。Receipt 守卫只审 issuer 的成对 Plan/Receipt，并精确允许原 rebind；其他 owner 写路保持原样。先让原受限 rebind 在 active 阶段跑出首个真实失败点。
2. `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：在原安装生命周期正向后，用同一独立 issuer 和先前 prepared Plan 调原 active resolver/rebind/Receipt Reader，核 paired revision、同键重放、错 CAS、错租户、撤权与失败无增量。仅必要时修改 `services/aos-api/aos_api/` 的最小生产接线，并保持 owner SQL 行为。
3. 用显式 Growth1.13 签名回执、隔离 PG/OCI 跑原 full-schema 专项及相邻测试；复核 SQL 身份、租户、资源清理、Plan/Receipt 配对及代码与本方案一致性。verification、m1 精确提交、AOS/Prime/D-wave 更新。有限进程未知提交/真实跨 UID 留下一切片，不能用本测试替代正式来源。

## 首轮 RED 后的精确修订

- 已进入原 active rebind；`CurrentControlPermission` 用 `isinstance(conn, psycopg.Connection)` 判断 BI 登录，而正式写工厂返回校验身份后包裹的 `_ScopedBIIssuerConnection`，因此误走全局 `meta_membership` SELECT，SQLSTATE42501。修复限于此类型判定及原 prepare 的同类判定：接受精确 `_ScopedBIIssuerConnection` 类型，继续由数据库 `current_user` 决定身份，不扩大表 GRANT 或替换权限函数。
