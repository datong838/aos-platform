# s3o-w-ab 第一切片｜原 BI prepare 的受限签名来源

## 上位方案与边界

- 231/625、D-wave s3o-w-ab：正式发行必须由独立受限身份读取当前签名安装、固定租户和真实 Agent/Receipt；当前真库只读、正式角色/IdP/六 Agent 缺失，首链失败关闭。只在一次性 Growth1.13 签名全 schema 库验证原服务，不启 Host/worker/Provider。
- s3o-w-aa 已证受限 resolver 能通过固定函数读到当前锁内候选，四张全局 Registry 表 SELECT 仍拒绝。本切片检查原 `SignedBIPlanPreparationService.prepare` 用此 resolver 是否与既有安装锁、六 Agent 锁、Plan/Receipt 同事务写兼容；不对默认 HTTP503、生产 migration 或当前 DB 做修改。

## 文件级步骤

1. 在 `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py` 将原 prepare 的 `preparation_resolver` 从 owner resolver 换成同一 BI 非 owner/NOINHERIT 专用只读工厂的 `restricted_resolver`。先 RED，记录原 SQL/权限失败与 Plan/Receipt 零副作用。
2. 若 RED 可由已授权最小接线修复，仅改该测试/必要的明确生产接线点；复跑原签名 full schema 测试与相邻专项，核同键回放、独立身份、无四表宽 SELECT、撤权失败关闭。若原服务只因配置/正式身份缺失而无法正向，保留 RED 证据并转独立可做的 Receipt Reader 受限读取，不造身份或伪造业务完成。
3. 复审原 `SignedBIPlanReceiptReader`/`SignedBIPlanRebindReceiptReader` 的当前成员资格、Plan revision、原 Receipt 配对读合同；先做正反观察，再决定是否新增精确函数。本切片不自动重发未知结果，不扩成完整 rebind/有限进程验收。
   RED 已见：原 prepare 改用受限 resolver 时，测试用 0600 passfile 在写事务前提前被 TemporaryDirectory 清理，resolver 返回 None；将该测试文件的生命周期覆盖原方法后签名全链复绿。随后同一受限只读 Receipt Reader 在 `meta_membership` SELECT 命中 `42501`。新增仅供隔离库的固定 `aos_bi_plan_membership_read_a0v_138(org,project,subject)`，只读、不加行锁，核独立登录与租户 GUC，PUBLIC 无 EXECUTE、BI 登录独享；生产 Reader 仅在显式受限 scope 下调用固定函数，默认全表路径不变。错租户/撤权负例与原 Receipt+Plan 精确配对仍须通过，不给 `meta_membership` 宽 SELECT。
4. verification、m1精确提交、D-wave/续接626、Authority/Prime同步。正式迁移仍需新全备、克隆全链、零执行窗口与真实 role→scope/IdP/六 Agent；真实跨 UID、rebind/有限 accept 单列下一切片。
