# b87 完整来源许可发行命令施工方案

## 目标与真实缺口
复用原 Proposal/Approval，形成具体来源许可的 typed producer/checker、独立 issuer 和同事务 issuance/head/RegistryReceipt。当前签名 Policy、canonical provenance、初始化协调锁仅是基础，不是发行授权。当前 Action 风险算法未识别来源许可，默认 R1/draftOnly，通用编辑入口也未保留专用身份。

## 顺序与文件级库存
1. 固定 `aip_issue_source_license` 身份、R2/maker-checker 风险下限、仅专用命令消费；通用编辑、seed、producer及原 Store 请求/批准防止伪造身份。新增 `services/aos-api/aos_api/aip_license_source_action.py`，修改 `aip_action_policy.py`、`aip_policy_activation_action.py`、`aip_action_service.py`、`aip_action_store.py`；新增 `tests/aip/test_aip_license_source_action_gate.py`。本次只交付此接线前置，完整命令不可标完成。
2. 新增 `aip_license_source_proposal.py` 的 typed target/request/checker，复用原 ActionStore 与 TransactionBoundConnectFactory。精确绑定 tenant/source/hash/provenance、明确许可与用途、有效期、installation ETag/current revision、selected release全元组、PolicyRef/hash；不从摘要、created_by或包MIT推导许可。OIDC actor与当前精确Owner membership共同锁；checker与maker不同，重新读源、当前签名Policy及Owner。原 Approval event/hash/version/expiry/withdrawal复核，不造影子审批表。
3. 新增 `aip_license_source_issuer.py` 和独立 issuer connection/provision specification。精确身份无成员/高权、不借Registry或BI issuer；最小函数执行权与事务内Receipt写权。先幂等键锁，再原Proposal/current-installation锁，再来源初始化独占锁；所有消费者相同锁序。重新读canonical build与原Receipt、frozen/current/未撤销/新鲜来源、当前Policy和Owner批准。提交前数据库clock_timestamp到期复核。issuance/head/RegistryReceipt一次commit，response先构造，异常0/0/0；重放先对账不重发。
4. 独立schema迁移仅一次性测试库，正式135库不迁移。函数定schema/search_path、PUBLIC零、FORCE RLS，runtime无issuer写权。旧Evidence无provenance不补权。新issuer无自动供给真实身份、无HTTP公开放权。
5. 真实PG验证合法Owner/独立checker完整批准→受限issuer发行→exact fact读取；拒错tenant/hash/Policy/ETag、同人批准、撤回、过期、冒牌producer、假issuer；实际PID竞争与SSI40001；同key重放、wrong-source key conflict、提交失败回滚；canary0。签名真实完整schema累计，并复核八实际facts接续。仅测试闭环，仍非自然经营首链。

## 本次验收
先保留专用Action未识别的RED，随后固定身份与所有通用入口阻断测试通过，原policy/action相邻测试无回归。生产未启用typed producer/checker的情况下，任何新身份必须 fail closed。不得把该前置作为完整发行或新审批权。

## 边界与回滚
m1单写，保护9个用户M；不push/其他分支/商城源/旧Run/Host/worker/Provider。当前135只读。仅新增动作受新约束，既有policy错误代码与普通动作路径不变。回滚为精确反向提交，不reset。后续每个实际编码范围须Task/Lease和RED；本方案不构成真实身份、迁移、外部效果许可。

## 执行器复审补充
当前 `aip_action_execution.py` 的 `_reject_bootstrap_action` 保留多个内部动作身份，但无来源发行；后续通用 `executionAllowed` 缺失默认 true。新增同一专用身份拦截，涵盖请求ID与snapshot ID任一匹配，独立于策略字段；专项 `tests/aip/test_aip_license_source_execution_gate.py` 先RED后GREEN。该补充先单独登记Task/Lease，未改变真实执行权限。
