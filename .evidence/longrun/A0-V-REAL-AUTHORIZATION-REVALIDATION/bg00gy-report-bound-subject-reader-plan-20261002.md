# BG00GY｜Subject 双签与精确 Report 侧证同快照读取方案

基线 m1 `389dc3bd`、AOS-001079、代码/隔离克隆 132，当前权威库仍118。本波是已批准 Subject 代码/隔离验证的一小段正式消费者接线，不产生当前库写入、Provider、Host 或自然 EvalRun。

## 上位依据和已读事实

- 231 总控 §3/5/6、231-1 N4/N5、231-5 §1/2/7 要求原生成来源、评测、审批到 Handoff 保真；栖月汇技术方案 §10.4 要求 Eval/批准在知识或执行晋升前独立存在。
- `aip_eval_subject_persisted_reader.py` 已在稳定 tenant snapshot 校验 Run、root、两身份、双 Receipt 和撤销，但没有读 `aip_eval_subject_case_proof`；`a0v_132` 已为该表建立同租户/Run/Case/Envelope、双 Receipt claim 与同 Run Report 的 FK。若 consumer 不读该表，签名结构结果可与任意 Report 并列而无消费层绑定。
- `ecommerce_analyst_stage_review_command.py` 读取原 AgentRun/Artifact/Usage/query/text 和精确 passed Report；原 `AipEvalRunner.run` 在 SkillTemplate 创建 Run 之前禁入。新 reader 仍不自动成为 Stage consumer，下一波必须从原 Owner 接入；不能仅靠本波宣布阶段评审或首链通过。

## 文件级范围与最小实现

| 文件 | 变更前 SHA256 | 动作 |
|---|---|---|
| `services/aos-api/aos_api/aip_eval_subject_persisted_reader.py` | `c2c66d75e962d8ae9ed5f7e8f1db44d49cd6018a66407be551a6f35a9b268448` | 给现有唯一 reader 增加必填 exact Report id/revision/hash；在同一 transaction 读取 sidecar 与 Report，核对双 Receipt ID/claim、封套、Report hash/Run/结果/时间；保留原双签验证和原 public v1 路径 |
| `services/aos-api/tests/aip/test_aip_eval_subject_persisted_reader_pg.py` | `203727ec0f94172b6f2fda8024fb0fc6b2e8589bee8668cebce53a854de267c9` | 先 RED：有双签但无 sidecar 应拒绝；错 Report/hash、结构结果漂移应拒绝；完整侧证可通过。测试数据只在 disposable PG，不能作为客户正式通过 |
| 本方案和 verification | 新增 | RED/GREEN、相邻回归、代码/方案复审和下波入口 |

调用合同：调用者仍必须通过原 Owner 重读正文/query/安装 fence，并通过 `read_stage_eval_report` 验证 Report 的 canonical hash/current/latest、Run 状态和审批；本 reader 只证明同快照持久双签与**指定** Report 行、单 case 结构结果一致。不能把传入的 Report hash 当权限，也不签原生成两次。当前不改 Stage command，因为合法 Subject EvalRun/Report producer、正式 issuer 与受限 writer 尚未接好，直接替换旧 Gate 会误放行或永远禁入。

验证：RED 单测缺 Report 绑定；最小实现后标准临时 PG Subject 专项及相邻签名/旧 Skill 证明回归，`py_compile`、`git diff --check`；无前端变化，浏览器不适用。风险是旧测试直接调此 reader 的签名改变（只有本模块 PG 测试引用，已搜索确认），同波更新。回滚为撤销本函数新增检查，保留已写证据；正式数据不动。

下一波：追合法 EvalRun 创建 Owner 与原生成事件，受限 writer 原子写 Receipt/Report/sidecar；Stage consumer 在 Host 同一稳定 snapshot 使用本 reader 和 `read_stage_eval_report`，且继续要求原生成与安装 fence。当前真库迁移/重启另走独立门。
