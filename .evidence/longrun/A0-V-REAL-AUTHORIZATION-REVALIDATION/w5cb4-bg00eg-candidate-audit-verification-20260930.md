# W5CB4 BG00EG｜七类候选与正式消费对照

基线 m1@17d7eed1、AOS-000994。只读代码核查，不代表当前实例候选已存在或正式业务通过。

| 类别 | read_candidates 谓词 | 目录/正式 reader | 结论 |
|---|---|---|---|
| responsibility_plans | 同租户 current head + frozen | source_catalog 同谓词；read_current_responsibility_plan_ref 另核 exact/hash | 候选条件一致 |
| data_policies | 同租户 current data_classification + active + from<=DB时钟<until | _load_guard_policy 相同生命周期/窗口，另核 canonical/hash | 未发现合法记录的额外候选误报 |
| egress_policies | 同租户 current egress + active + 有效期 | _load_guard_policy；Network/Runtime 的 exact Egress 绑定另验 | 数量不能证明绑定一致 |
| network_policies | 同租户 current head + active + 有效期 | _load_network_policy；a0v116 active INSERT 门仍由独立消费路径负责 | 无理由在计数中复制批准消费 |
| quota_policies | 同租户 current quota + active + 有效期 | _load_governance_policy 的 quota 分支 | 语义一致 |
| budget_policies | 同租户 current budget policy + active + 有效期 | _load_governance_policy，另核绑定的 BudgetRevision | 数量不能证明预算依赖匹配 |
| budgets | 同租户 current budget + active + 有效期 | read_current_budget_ref 另核 development/CNY/hardStop/block；这些均为 BudgetRevisionCreate 的 Literal | 未发现符合创建契约的额外误报 |

现有 source_catalog 仅枚举职责和运行策略，另外六类由选中的 RuntimePolicy 精确引用推导，并非六个独立选择器。八个 count 均大于零不证明存在一个完整匹配组合；read_candidates 模块和既有测试已明确 all_present 不是运行授权。正式消费仍必须验证 payload/hash、依赖 current、最终锁后有效期、权限和安装绑定。把这些都复制进候选 SQL 会新增第二套授权逻辑，违反 231-1 唯一权威与本波最小修改要求。

验证命令：
- `scripts/memory/memory-status --json`：exit 0，AOS-000994，强一致投影均 CURRENT，eventual Codex note PENDING_ASYNC。
- `scripts/memory/memory-validate --json`：exit 0，GREEN。
- 逐文件读取 runtime_configuration_candidates.py、configuration_source_catalog.py、aip_runtime_configuration_sources.py、aip_runtime_configuration_authority.py、aip_budget_contracts.py：exit 0；上述矩阵可据同名函数复核。
- `git diff --check`：exit 0。没有修改生产代码/页面，无新逻辑，因此本波未新增或重跑代码测试，也没有浏览器业务验收。

本波结果：结束候选广扫，没有证据支持再改计数器。回到 BG00EE 的具体网络消费缺口：现有 `precheck_network_activation` 在取得后续批准/成员/依赖锁之前只取一次应用时间；下一波 BG00EH 针对等待期间到期场景设计真实隔离 PG RED，验证最终时效，修复后继续非特权原子消费者角色/函数合同。只读预检本身不能开放 active。

Goal 回读 active；这证明本次已恢复，不证明所有断联恢复机制已验收。当前库未查询/写入；Host/worker/Provider 未启用；无商城源、旧 Run 重放、手工 run_definition 或 push。
