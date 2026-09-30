# W5CB4 BG00dp｜签名 BI 模板 approved 准备态克隆验证（进行中）

## 实测对象

test-only `colima-aos-a0v-test-only/aos-bg00dl-isolated-pg`，卷 `aos-bg00dl-isolated-pg-data`，库 `aos_current_preview_20260927`，127.0.0.1:18440。连接以 `psycopg` 只读事务执行；代码测试使用独立 pytest PG。当前真库无写。

| 检查 | 命令/来源 | 退出码与结果 |
| --- | --- | --- |
| 克隆安装/Artifact 只读查询 | `PYTHONPATH=services/aos-api uv run --project services/aos-api python -`，使用 `_clone_connection_parameters()`，查询 `bundle_installation/current revision/composition_lock` 与 `asset_bundle_artifact` | 0；旧 growth1.11 和新 growth1.12 各 approved@3/active NULL；新安装 `42785d78-5914-4a54-a078-e5d2c7f48481`；模板 artifact digest `sha256:76036401433342f95328c43ecbcb618deb3c6adba335532b6bfc11af896d0f3b`。 |
| 独立签名快照 | `RegistrySnapshotReader(ReleasePolicy(FileTrustRootProvider(clone-only-trust-roots.json)), clone_readonly_connection).read()` | 0；growth1.12 内容 hash `sha256:ca604f9b18dba305dfaa54bc6e47006e512fd6c810888fdeb41a223057be6bd1`，签名 fingerprint `sha256:f1d45a30e2f4d25891962a3c2af9dde0f55811b8732579341112b0f1c4192459`，当前 evidence revision `sha256:9b67f25f5910f1588d47e538ebb07bece3278ac6de0897de680ac947ce0bc63a`。 |
| 签名镜像重验 | `ManifestLoader({'a0v-growth-112': signedTree}, trust_roots=clone_roots).load('bundle://a0v-growth-112/solution.ecommerce.growth/1.12.0')` | 0；镜像内容 hash 与快照相等；模板 artifact ref/digest 与数据库相等。 |
| 准备态选择器 | 克隆 DB URL、`AOS_BUNDLE_ROOT=signedTree`、`AOS_BUNDLE_TRUST_ROOTS_FILE=clone-only-trust-roots.json`、`AOS_BUNDLE_SOURCE_ALIAS=a0v-growth-112` 下调用 `ApprovedBIPreparationResolver().select(TenantScope(...))` | 0；`org-org/dev-project` 正向返回上述安装 ID、exact artifact ref/hash 与 `templateId=ecommerce.business-investigation.readonly`；`dev-org/dev-project` 返回 None。没有写 Plan、active、binding 或运行端口。 |
| 负向只读/内存探针 | 同一选择器：内存重复 approved 行、精确 growth lock fingerprint 漂移、持久 artifact alias 替换、仅旧 trust root、临时复制签名树并修改模板字节 | 0；五类均返回 None。首次 alias/lock 探针只改动了非目标行，未形成有效否定；修正为修改所有候选行后重跑，均拒绝。签名原树未修改。 |
| 新增及相邻单测 | `uv run --project services/aos-api pytest -q services/aos-api/tests/aip/test_aip_responsibility_template_authority.py services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py services/aos-api/tests/test_ecommerce_analysis_compilation_roles.py services/aos-api/tests/test_ecommerce_business_investigation_aip_readiness.py --disable-warnings` | 0；58 passed。 |
| 静态检查 | `python3 -m py_compile services/aos-api/aos_api/aip_responsibility_template_authority.py`；`git diff --check` | 均 0。 |

## 结论和未完成

独立只读准备态来源能从 test-only 的唯一 approved growth1.12 安装，组合当前 Registry ReleasePolicy、签名镜像、精确 lock 与 artifact 字节导出 exact ref。它不改变现有 active 生产解析器；没有凭此授权当前真库或 Host。

Plan builder/materializer 仍使用静态 ref 且 fail closed，尚未接入此准备态选择器；业务读取端也仍按旧静态 ID 比较。下一切片需给配置创建使用专用准备态 resolver，业务使用独立 active resolver，并以签名 payload `templateId` 绑定产品 code。正式 source alias/信任根/独立身份尚未配置，当前首链 pending。
