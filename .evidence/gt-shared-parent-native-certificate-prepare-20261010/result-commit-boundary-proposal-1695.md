# 共享父风险：准入与结果的提交边界候选

状态：设计候选，未实施、未授权执行；原单次联合提交约束及七个拒绝门继续有效。基础 AOS-001695。

## 已核事实

R29 原完整准备前缀中，manifest/四腿证书与 Source/双父预算属于尚未提交的原 caller。独立 READ ONLY observer 看不到该 execution 的 manifest/证书（均0），原 caller 状态 in progress。独立 test-owned Executor Owner 插入明确标注的无签名 FK 探针，被原 case_result→manifest 外键23503拒绝；探针事务 aborted、行0。后继组合原测试在 Judge 期限门失败；原 caller 最终 aborted，独立11张风险/结果表0，七 guard 原 body hash 未变。不得把这个 compound FAIL 改称全轮 PASS。

原 v2 Target reader 要求 result origin xid != caller xid 且 committed。该条件若直接套入当前 v3 同事务准备阶段，就没有可见的 parent manifest 给独立结果 writer。这是“直接复用旧来源前提”的不兼容证据，不是所有可能协议都不成立。v3 签名只是必要描述；不能用签名、test admin insert 或伪造 committed 状态弥补。

原 content worker 源码顺序是 submitted→conn.commit→invoke→结果持久化；未知结果进入 unknown/对账，不重发。该源码顺序不是任意借用连接下实际持久化的证明，后继必须用真实隔离连接观测 dispatch 前独立可见的 Intent 和风险。不能 suppress commit 后仍称原安全发送边界已保留。

## 必须先明确的原子范围

候选 A：准入事务原子地提交 Source/当前授权、双父风险、完整四腿 manifest/certificates、唯一 Target Intent 和 Judge pending dependency、初始物理风险以及不可变准入 receipt；外部调用与结果在已提交准入之后由唯一执行 Owner 接续。结果每次提交必须消费同一 receipt/Intent、实际 transport/Usage/费用及当前撤回头；unknown 保留风险且只读对账，不重新准入或派发。同一原始父持有与初始账不得重复申请。这是待审协议边界，不能把当前 prepared_only 数据自动提升为准入 receipt。

候选 B：若仍要求 Target/Judge 实际结果都先于那一次联合 COMMIT，则需说明怎样同时保持“唯一 Intent/风险在外部效果前已经持久化”、rollback/unknown 风险不丢失及原独立 committed-origin。原 worker 与当前 FK/可见性模型不能直接实现它。不得通过删除 FK、假结果、关闭 trigger、把同 xid 称 committed 或将实际 COMMIT/WAL期限替换为决策时间来解决。

在原子范围及完整协议审查之前，不实现使旧 guard 放行的变化；继续完成可独立核查的原真实 Intent/journal/结果 provenance 协议。M4/模型质量差异不是这个局部协议的替代理由，也不改变整个 Goal 状态。

## 后继具体文件包（先合同与精确 Lease，暂不编码）

- 新私有协议：`services/aos-api/aos_api/aip_model_shared_parent_admission.py`；`aip_model_shared_parent_result_authority.py`；`aip_model_shared_parent_result_reader.py`。
- 原接线（仅方案决定后在各现有 Task 精确 scope 串行施工）：`aip_physical_capacity_occupation_authority.py`、`aip_model_eval_execution_owner.py`、`aip_eval_runner.py`；任何复用 worker 的连接/COMMIT 语义必须先原生验证。
- 原生验收：`services/aos-api/tests/aip/test_model_shared_parent_admission_pg.py`、`test_model_shared_parent_result_reader_pg.py`，另含未知结果/持久化失败/跨期限/撤回/并发唯一 Intent/租户 canary/预算与物理风险不重复的完整矩阵。
- 迁移只做新的 additive 版本；精确编号须先核最新代码迁移头。当前权威真库仍只读，部署/签名来源/Root/Host/Provider 独立正式门不因本设计获得许可。

## 可收口验收

首次实际 dispatch 之前，由独立连接验证同一已知提交的唯一 Intent、所有适用风险账和可信 receipt；不以程序调用了 commit 方法代替持久化观测。dispatch 为0或1；未知不能自动重发或释放。Target结果完整原字节/请求响应/Usage/hash/producer xid、Judge精确Target输入/证书和当前撤回头必须实际对应；各后继风险和费用事件保持同账户同父义务。最终发布/current gate/Resolver消费完整证明，未具备证据则失败关闭。上述全部仍待真实证据，不宣称当前 candidate 已实现。
