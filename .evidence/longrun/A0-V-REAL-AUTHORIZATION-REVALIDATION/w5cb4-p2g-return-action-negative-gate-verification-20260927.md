# W5CB4 P2g30a RETURN Action 负向禁入验证（2026-09-27）

## 结果边界

`NEGATIVE_GATE_GREEN / FORMAL_RETURN_PROPOSAL_STILL_UNWIRED`。这是一段必要的失败关闭修复，不是正式返工提案或真人批准的成功证明，更未解除内容 Host 的 `revalidate/execute` 双重禁入。

## 方案、RED 与最小代码

- 上位 231-5 §5/6 要求退回新版本与新批准、旧批准不可延用、预算预留先于能力调用。P2g29b 已证明原 executing Task 不能新建通用 Plan/ImpactPreview。P2g30 方案据此限定 RETURN 专属六项 exact payload；本子步在权威生产者实现前禁止半成品提案持久化。
- RED：`test_ecommerce_content_repair_action_binding.py` 的 R1/draftOnly RETURN 与 R2 残缺 payload 两项原始运行均 `DID NOT RAISE`。现补充精确键但无 current authority、直接遗留提案 checker 的负例。
- 新增 `ecommerce_content_repair_action_binding.py`：仅对内容生成且带任一返工专属字段的请求生效；服务端重算风险，R2/R3 maker/checker、可执行、非 draft-only 且最少一次批准才继续；缺/多六项或带通用 Preview 拒绝。即使键齐全，在当前 target/Host/Brief 的生产者未接线时仍拒绝。`aip_action_store.py` 的 create/revise/submit/direct proposal 既有 `_internal_request_binding` 与 decide/replay 既有 `_internal_proposal_guard` 均调用此门；非 RETURN 动作保持原路径。
- 因当前无合法 RETURN 正向生产者，本子步不计算或持久化任何返工 `action_binding_hash`，不制造批准或预算占额。不改表、迁移、通用预算 Store、Host/worker 配置；原库和商城源未访问。

## 新鲜验证与风险

- RED 后专项 `4 passed`；与既有返工批准读取、内部 cutover、普通 Action/Preview 绑定的相邻累计 `19 passed`；`py_compile` 与 `git diff --check` 通过。测试仍是单元/既有隔离 PG，不是栖月汇正式安装/真人审批。
- 本门对包含返工专属字段的旧/异常提案 fail-closed；没有 RETURN 字段的首生内容提案未改动。结构性风险：公共 Action 风险缺省为 R1/draftOnly，P2g30b 正向需显式 R2 并经当前 ActionType、唯一 ReturnDecision/queued attempt、正式冻结 Brief/Receipt、当前安装/能力/金额及 checker 复核。不能以此次负向 GREEN 宣称预算或自然续跑。
- 下一波 P2g30b：同一事务复用已有 `BoundContentReturnTarget._source(require_queued=True)` 和 `require_frozen_repair_brief`，证明唯一 target 与当前 dispatch/Capability/预算上限，再生成稳定绑定 hash，公共提案/不同 checker 决定/消费端与预算只读门同库正负验收。若当前身份/权限无法组成，保留禁入并继续不依赖真实实例的主线研发。
