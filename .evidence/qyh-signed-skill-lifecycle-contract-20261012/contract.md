# 新 Skill 专用 producer 合同 v1：生命周期、真实执行与登记

## 依据与本波事实
复用 231 的 A1 首链依赖、BG00u 直接 Skill 禁入和 BG00ac 原子证据边界；原实现已完成签名消费者和登记器，不重做这些实现。当前 HEAD 与精确代码 SHA 见 observed.json。原普通 runner 依次独立提交 QUEUED、RUNNING、Report、SUCCEEDED，失败时另尝试 FAILED。atomic writer 的 preflight 要求已有 succeeded Run。这两个入口不能简单拼接。实验库两个 RR/READONLY 快照没有 aos_aip_eval_writer 角色；不借管理员或 runtime 权限代写。该结论仅适用于实际核验的 qyh_source_contract_20261011，不外推正式库缺角色。

## 目标和文件级实现顺序
1. 新增 services/aos-api/aos_api/aip_signed_skill_eval_runner.py：独立专用入口，普通 aip_eval_runner.py 的 Skill/Model guard 保留。输入必须包含完整当前 EvalContract/Suite/Dataset 精确引用、脱敏来源、真实 Owner/审批/预算/网络授权快照、独立 Target/Judge executor 及 writer。缺任何项在创建 intent 和调用 executor 之前拒绝。
2. 新增 services/aos-api/aos_api/aip_signed_skill_eval_intent_store.py 与独立 Alembic 迁移（具体 revision 须开码时核最新迁移图）：服务端持久 intent、每 case/purpose dispatch 序列、结果摘要与已验证签名引用、预算关联、未知状态、expected-version CAS。唯一键 tenant+idempotencyKey，稳定随机 Run ID 创建一次；不同合同同键冲突；不复用旧 Run。写角色独立受限，SQL/RLS/不可变约束，不能靠 Python dict 或文件锁保证幂等。
3. 修改 services/aos-api/aos_api/aip_eval_writer_atomic.py 与 aip_eval_writer_authority_preflight.py：保留已有 succeeded Run 登记调用兼容；另提供仅新 producer 的终结接口，不全局降低 preflight。新接口同一 SERIALIZABLE 连接锁住 exact 新 Run/intent、核授权和双方全量签名、CAS RUNNING→SUCCEEDED 及 event、登记 Receipt/Report/Proof、完成 intent，事务成功前不发布 Report。原 preflight 在该未提交事务中读到 succeeded；晚期任何失败回滚所有终结写入。不能在事务外先改成功再调用旧 writer。
4. 原 aip_eval_authority_store.py 若需提取 connection-bound CAS/event helper：只提取 SQL，保留现有调用的事务语义、租户、version 和状态转换校验。不可把原内部 conn.commit 的函数注入同一连接而假定它不会提前提交。
5. 扩展 aip_eval_writer_reconcile.py：同 tenant/exact Run/intent/Report 与全 case receipts 的只读 RR/SERIAL 快照。只有完整相同 proof 和最终版本才 COMPLETE；另检查已派发 executor 结果。UNKNOWN 不调用 Target/Judge、不重新登记；已证明执行完成且登记未提交仅可在新明确登记授权下重试登记，不能重执行。现有 report reconcile 不能单独证明外部未执行。
6. 新增 services/aos-api/tests/aip/test_signed_skill_eval_runner_pg.py：新临时全库+真实独立签名+原 writer/readers；原成功执行路径及下列负向/并发/故障测试后再接正式入口。独立角色 ACL 先在隔离库迁移并验全部旧权限路径，再另立正式迁移/备份/恢复/零执行窗口；不直接改当前库。

## 真实调用协议
A. 准入：原权威查询同一租户、exact hash、有效期/撤回、Owner和当前审批；预算预留和实际费用协议复用原正式合同，不能只看额度存在或历史批准。私钥与连接文件只在专用受限入口，不入 Receipt/日志/argv。development principal 不能授权。
B. intent 创建：持久请求 hash 含上下文、cases、inputs、expected refs、双方身份和预算，不含密码。只创建全新 QUEUED Run；稳定 Run ID 和 case receipt identity 绑定。不以 status label 当完成证明。
C. 派发：在任何 Target/Judge 外部调用前，CAS 并提交 dispatch intent。同 scope/key 并发只一个 winner；其他只读结果。dispatch 已存在/未知永不再调用。CAS 失败、commit 断联或 Timeout 先只读对账；无证明不能重试。不在数据库长事务中调用网络。
D. artifact：原 resolver 读回真实字节并重算 hash，验证脱敏 Dataset/source/case，不修改 input。Target 输出字节的规范 hash、发生时间、双证书/签名、Run/Suite/case/tenant/executor exactrefs 必须匹配原 verify_execution_pair；Judge 输入绑定 Target output，签名判定/actual/expected/detail 与 Report 同源。不使用普通 TargetExecution/JudgeExecution 直接构造被信任结果，不把测试 key 注册正式 issuer。
E. 原子终结：逐 case 的完整真实签名及当前 root/identity 重新预检，状态/事件/Receipt/Report/sidecar/intent 同事务；正常评测不通过仍可执行成功，但 gate_passed 按原阈值算，不能擅自调阈值。Target/Judge异常或缺证据不能生成通过报告，不自动 publish/evaluate Skill 或启动工作台。
F. 中断：只读核对实际数据库、dispatch 和 executor 查询协议。持久 UNKNOWN 不是失败且不释放可能已消耗预算。登记 commit 未知也不能调用旧 writer再次INSERT；先 full-proof reconcile。明确终止失败使用正式恢复入口，保持既有证据和预算对账。

## RED 与验收矩阵
- 未配 writer、issuer、Owner、审批、预算、网络任一缺失：intent/Run/Target/Judge/Provider 调用全零。
- 正向真实签名：新 QUEUED→RUNNING→SUCCEEDED、Report/两 receipt/sidecar/event 完整原 reader 通过；原Gate/publish另门。
- suite/input/output/expected/hash/tenant/time/certpurpose漂移、过期撤回或同一 Target/Judge 身份：原 preflight 拒绝、无成功终态。
- 晚期 Report、Receipt、sidecar、event 或 CAS失败：Run仍原版本、成功事件/Report全不存在；保留可对账已执行结果，不重新调用。
- 双进程同key/不同合同、派发commit未知、Target已执行后断联、Judge未知、终结commit未知：每 purpose 最大一次调用，UNKNOWN仅读取；外部模拟故障须明确标为隔离测试，不当正式运行。
- 原 Logic/媒体/Scope/defaultoff/Model guard 及发布消费者累计回归；跨租户 canary 零副作用。

## 发布与产品约束
只完成代码/隔离 PG/签名测试不能满足正式身份和内容审批。登录、发布、签发、预算四类身份职责不能互相替代。正式执行器接入经上述真实门后，先新独立评测及原消费者/发布链，再当前安装配置/Runtime禁入复验、八台真实浏览器和自然经营闭环。用户历史135安装/65Runs/12停用Schedules保留，不补签或回放。所有候选文件列为下一代码波范围，本波尚未实施；不能给用户承诺仅安装就可用。
