# BG00FD 网络配置提案响应丢失后的精确只读对账

## 开工卡 / 第2/9步
- Task W5CB4-BG00FD-20261001；m1@72f0ca1c；AOS-001018；单写者。
- 原目标：231 A1/E17/BG-00 首链必要网络配置产品链。复习231 §7.2、231-5 §5/8、八工作台公共产品契约§4/11、411接续和当前01/06。
- 缺口：activation-proposals 创建响应丢失时现有 GET 需已知ID、list仅最近500条；不能精确恢复原请求。审批与消费已有inquiry，不能以重发创建代替对账。
- 本波验收动作：原创建已提交但调用者无响应，用原租户/发起人/幂等键/候选/If-Match/expiry读回精确proposalId；未见记录始终unresolved，不授予重发或激活权。

## 合同与最小实现
- 新 POST /v1/aip/runtime-guard-policies/networks/activation-proposals/inquiry：复用 NetworkActivationProposalRequest、If-Match、Idempotency-Key 和 require_principal。POST仅承载查询体，全流程connect_read_only/repeatable-read。
- OIDC principal必需；租户与actor取认证结果不取body；精确查询scope+key+created_by，不向另一actor泄漏proposalId。
- observed 200仅返回status/proposalId；unresolved 202没有资源引用且绝不代表未执行；原key不同request或action返回conflict409且不泄漏ID。未认证403、非法输入422；DB连接/读失败503固定码，不能当未执行。
- 提取原producer的纯候选到CreateActionProposalRequest构造（无行为变更）；提取原store的canonical创建request hash（序列化保持字节合同）。inquiry使用持久action revision/risk/policy和原body重算，匹配历史request hash；不读取当前head或metadata作新的准入，不因proposal到期/已批准/依赖变化丢失历史对账能力。
- 只读连接必须验证transaction_read_only/current_role/tenant GUC；不调用producer/issuer/consumer、不写marker、不行锁、不迁移。
- 不改UI/旧API返回合同，当前真库、Host、worker、Provider不动；前端下波复用现有收件箱。没有浏览器通过声明。

## 文件清单与前hash
- `services/aos-api/aos_api/aip_action_store.py`：5df6c4d4d29a1164647bc6cc595a07716ddbf5335560582e867db5a2cf2d791e
- `services/aos-api/aos_api/aip_network_policy_action_producer.py`：42379d56952e91d66903ad9bb47369f895c4206c3441ad808990d0a9a710e914
- `services/aos-api/aos_api/aip_network_proposal_reconcile.py`：NEW
- `services/aos-api/aos_api/routers/aip_runtime_guard_policies.py`：67ad7df3b38072b1821d72475b64bd4fc1805d3a40237c2f77c97af8cc41fba8
- `services/aos-api/tests/aip/test_network_proposal_reconcile_pg.py`：NEW

## 验证、风险、回滚
- RED：新测试缺入口/模块。专项：隔离临时PG真实producer产物、签名HTTPS HTTP inquiry、未见/同key不同输入/他actor/他tenant、过期后仍历史可查、未提交结果不授予重试、readonly事务与计数无变化。输入注入拒绝。
- 累计：producer旧专项、issuer application、consumer application、network atomic consumer；旧root client测试在累计末尾避免删元数据干扰。
- 风险：观察历史创建不等于当前批准或激活；UID/OIDC正式材料缺失仍阻断部署。字段/hash抽取不得改已有幂等合同；用原公式对照验证。
- 回滚：精确revert本波代码提交即可；无schema/正式数据变更。
- 退出：专项累计通过、diff复审、verification、精确m1提交、Delivery/CAS/sync/Prime回读、412与D-waves登记。
- 下一BG00FE：将该查询与issuer decision-attempt接入现有产品读取/审批入口，先找回缺失的browser-pilot验收能力；页面不能调用手工消费/Run。
