# W5CB4 E17-s3o-w-c｜原职责 Plan 写者与共享 Receipt 只读盘点

日期：2026-10-03。复习 231-3/4/5/9 与栖月汇全店经营方案后，按本波文件级 plan 搜索服务代码的 Plan/Receipt DML 与调用路径；不读商城源、不连接或写当前库。

| 路径 | 可复核位置 | 事实及设计影响 |
|---|---|
| 原 Plan Store | `aip_production_contract_store.py` 的 `create_*`/`revise_*`/`freeze_*`，`_head`、`_advance_head`、`_receipt` | create 插 head/revision，同事务写共享 Receipt；revise/freeze 先 `FOR UPDATE` head、进版、同事务 Receipt。 |
| 包裹及 HTTP | `ecommerce_business_investigation_aip_authority.py`、`routers/aip_production_contracts.py` | BI 三条 in-transaction 与 generic HTTP 三条均调用原 Store，必须保持原幂等、依赖和事务边界。 |
| 第二 Plan 写者 | `aip_responsibility_assignment_store.py` successor 路径 | 直接 INSERT Plan head/revision，并写 successor 自身权威；仅封原 Store 会漏掉此写者。 |
| 共享 Receipt | `aip_content_draft_store.py` 的 `INSERT INTO aip_production_contract_receipt` | 不能给 Plan issuer 独占整张共享 Receipt 的 INSERT；若保留 runtime 的泛 INSERT，单纯检查 Plan operation Receipt 容易伪造。 |
| 原数据库权限 | `w2_001_brief_evidence.py`、`w2_002_eval_responsibility.py` | Plan 与 Receipt 的旧广义 runtime 写权仍需独立发行/收权；RLS 只隔租户，不隔同租户发行者。 |

命令：`rg -n 'create_responsibility_plan\(|revise_responsibility_plan\(|freeze_responsibility_plan\(' services/aos-api/aos_api -g '*.py'` 与 `rg -n '(INSERT INTO|UPDATE|DELETE FROM) aip_responsibility_plan_(head|revision)|(INSERT INTO|UPDATE|DELETE FROM) aip_production_contract_receipt' services/aos-api/aos_api -g '*.py'`，只读 exit0；逐段读以上五个文件。`git diff --check` exit0。

本波不新增发行代码、DB migration 或当前库授权；没有把调查当成正向配置。下一步在隔离库先写三条 Plan head 写路径与共享 Receipt 互不破坏的 RED，细化 operation 级 issuer 证明及版本锁序，再做最小实现。正式实例 OIDC/独立凭据/Host Owner 仍缺，Host/worker/Provider关；Goal active。
