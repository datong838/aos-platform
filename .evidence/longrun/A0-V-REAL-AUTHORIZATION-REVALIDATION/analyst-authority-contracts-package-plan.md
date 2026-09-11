# 经营参谋权威领域合同包化方案

日期：2026-09-12

基线：`b8cb2ce9`

状态：实施完成，后继领域规则拆分待办

## 产品与技术判断

栖月汇经营链要求经营参谋只消费受治理的 Data OS / Ontology / AIP 投影，工作台 DTO 不得
携带源库凭据或不必要 PII；经营参谋只形成可追溯的 Insight、Decision、GrowthPlan、TaskGraph
与 EffectReview，不直接改价、触达或发布。领域包应拥有这些领域对象的版本合同，但租户、
Artifact、Eval、Task、Receipt 和数据库权威继续由平台 Owner 掌握。

当前 `ecommerce_analyst_authority_contracts.py` 是 29 项增量迁移的公共领域 DTO 根，目标包文件
尚不存在。若直接复制其 `aos_api.aip_contracts` import，OCI 包会反向依赖平台私有实现；若让
平台改为 import 包，又会让未安装包成为宿主启动依赖。因此本波采用双侧版本兼容：包内建立
独立、同 schema 的严格 DTO，平台旧路径保持不变，以自动化 parity 测试防漂移。

## 本波范围

- 新增 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_authority_contracts.py`。
- 包内只依赖 Python、Pydantic；本地定义 camelCase 严格基类和只含 `orgId/projectId` 的响应
  Tenant DTO，禁止依赖 `aos_api`。
- 完整迁入领域枚举、exact ref、revision chain、Insight、Decision、GrowthPlan、TaskGraph、
  EffectReview 和 Receipt DTO 校验；不迁移 Store、事务或执行逻辑。
- 新增包/宿主 JSON Schema 全量 parity、代表性序列化 parity、负向校验和隔离 import 测试。
- 不修改平台生产 Python，不注册 operation，不触碰 Candidate、OCI、Registry 或 Installation。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_authority_contracts.py` | `d069b6b4339edc16f7c8644c3fbb538edc24683a798cfd93a7bba3d3c7b3722a` | 验证输入；保持宿主兼容文件不变 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_authority_contracts.py` | new | 独立领域 DTO 合同 |
| `services/aos-api/tests/extension_runtime/test_analyst_authority_contracts_package.py` | new | schema/序列化/拒绝/隔离合同 |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `7dfb5567ba15a3e8dbe832e2c8eae730c8d061467f4015718fd973377f72bacc` | 登记 9.9 切片 |

## 退出条件与下一门

包/宿主全模型 schema parity、代表性对象序列化 parity、既有宿主合同测试、独立进程禁止
`aos_api` import、编译和 AR2-7 closure 全绿后提交。下一波以该包内合同为根，拆分最窄的
纯领域规则模块；29 项整体仍保持 PENDING，直到正反依赖与运行装配闭合。
