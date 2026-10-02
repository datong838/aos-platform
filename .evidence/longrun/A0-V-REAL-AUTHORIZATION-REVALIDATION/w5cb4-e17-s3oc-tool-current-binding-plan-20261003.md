# E17-s3o-c｜ToolBinding 当前撤销门文件级计划

基线 `m1@5fcc02e8`、`AOS-001187`，当前真库 `aos_current_preview_20260927@a0v_135` 只读。上位 231/231-9/49-W6-01/128-W-L20 与 D-waves 下一波已复习；本切片只做 ToolBinding，AgentInstance 另证。

1. `services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py`：在 disposable PG 给 `org-org/dev-project` 建立 active ToolBinding、所属 AgentInstance 和 exact CapabilityBinding，走原 Resolver Receipt → READY Plan；之后分别停用 Tool、暂停实例/能力、改版本/归属，要求 Plan GET BLOCKED、freeze无 Receipt。先 RED。
2. `services/aos-api/aos_api/aip_production_contract_store.py`：只改原解析 Receipt 消费点，复用原 Resolver 当前候选判断并比较不可变 Binding refs；写准入行锁精确 Tool/所属 instance/CapabilityBinding，避免检查后并发撤销；只读 GET 无锁。不得以租户级其他绑定补位，也不改真实库或已有 Receipt。
3. 原路径正向、撤销负向、两连接并发、相邻解析与内容安全回归；核方案和代码一致性，verification 后 m1 精确提交、Task/Authority/Prime/01/06/D-waves 同步。正式 Tool 绑定和首链仍需当前实例授权证据，隔离测试不等于业务成功。
