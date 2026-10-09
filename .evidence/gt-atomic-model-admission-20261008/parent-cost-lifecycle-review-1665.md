# 父风险生命周期复审与下一波施工合同

原生只读调查成功（不是业务 GREEN）。精确保留库 aos_test_ff40de426907_ti4_test / cluster7694680278363095064，transaction_read_only=on、迁移头见结果。Eval/Judge CHECK state=held，UPDATE/DELETE/TRUNCATE append-only；独立 Judge held1 来源相邻测试，不是原 wholeplan 两父提交（不能混认）。原两个类分别只有 hold / require_current_parent，没有 submit/settle/release。普通 store 面向 invocation_id 与普通 reservation 私有来源，不能拿相同 UUID 当新 purpose 授权。

原 _actual_from_usage 从 reservation 原 pricing_ref 和真实 UsageReceipt 计算，任意 kind 无价格直接拒绝；本库两个 price 三价均 null 且有 developmentAuthorization。原 cost_pending 是普通调用完成且费用未知，保持原桶风险，不等于 Eval/Judge 已可调用或释放。当前代码与库一致保守拒绝，未发现需要放宽的既有 bug。

下一波精确产品范围仍为原 atomic Task 下 aip_physical_capacity_occupation_authority.py、aip_physical_capacity_occupation_contracts.py、test_physical_capacity_occupation_pg.py。设计追加私有 whole-parent lifecycle，不 UPDATE 旧 held 行、不改 ordinary store、不减少 shared_risk_totals；原 parent hash/approval/price/currency、完整 plan hash/四腿、producer provenance 都必须绑定。父风险从 held 到 active/unknown/cost_pending/known_complete 仅用不可变事件，当前头由可信 producer 导出，runtime 不可 DML；unknown/费用未知不得通过 TTL、结果成功、null=0 或用户输入 actualMinor 释放。

分开实际 inflight 与父风险：已知 transport 完成可按可信终结证据释放物理并发，但费用未定父 cap 仍全量占用；unknown transport 两者均保留。后续下一腿如果需要额外费用上界，没有真实原来源则不准入，不能把父 cap10解释成各腿10/5/1。完整两case四腿不可遗漏。known_complete 需全部腿真实 no-effect 或真实 Usage+可引用最终价格/费用证据，费用累计 <= 原父 cap；既有 ordinary calculated price 缺失无法补成完成。

先做全父生命周期原生 RED（same caller、全腿coverage、unknown/price null/replay/foreign tenant/runtime/并发争用/提前约束及COMMIT），再最小私有实现；default migration 与 joint finalizer 拒绝维持，直到 Source实际截止、真实token、joint/transport/root来源全部闭合。此设计不独立授效果；尚无真实费用来源，测试值仅测试标记。浏览器不适用于只读库/协议调查；无新 Prime PASS，人工对原源hash与catalog复核。计划、记录、提交不代表完整Task Delivery或自然首链。

过程命令诊断：一次 zsh 未匹配 settlement glob 使搜索未执行，一次错误文件路径返回缺失；后续使用明确存在的原 store及源码路径复核，没有重发外部动作。本脚本单次成功，数据库修改0、Provider0。未修改产品、旧数据、Goal或其他分支。
