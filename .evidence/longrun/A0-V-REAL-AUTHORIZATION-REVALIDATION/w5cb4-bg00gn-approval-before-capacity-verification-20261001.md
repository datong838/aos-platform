# BG00GN 审批先于容量预约 verification

2026-10-01；基线AOS-001054/m1 46726af5；七strong CURRENT、validate GREEN。231-5 §1/4/5/6与447先复习，计划与主Task/补充TEST Receipt已登记。真实库未连接，无迁移、重启、Provider、商城读取或旧Run重发。

## 改动与一致性复审

- 原来源准备增加显式before_capacity；capacity intent精确pending0/claimed1 token、current103、真实queued/version1、AgentRun/Skill/TaskRun身份、唯一当前容量池token覆盖；沿原Review/Plan/安装/Runtime/模型/配额/费用来源，未制造budget intent或批准。
- 原执行路径保持budget intent/current104/running、reserved未过期及token覆盖，补当前池精确route/model/provider检查。审批前资源配置检查不占容量。
- source envelope及binding domain升级v2：固定业务来源/原Receipt/Plan hash/AgentRun请求/安装代次/模型/预算/额度/期限，排除瞬时Capacity引用与expiresAt。期限不再被尚不存在的预约限制，仍<=15分钟、Quota和Budget期限。旧v1不转换不延长，复验不一致拒绝。
- 共享预算authority的只读批准核验可读审批前来源；真实reserve传入policy/price/key必须读执行阶段来源，缺预算意图或容量仍拒绝，不会提前held。原exact ref/金额及maker/checker权限门保留。
- CapacityOwner在preflight及claim事务核正式首生批准，普通旧content批准不代替首生来源批准；开始转换时在同一外层事务再次复核，TransactionBoundConnectFactory将原AgentRunService/CapacityGate的commit收归外层。提交前数据库clock_timestamp核同一批准有效，过期回滚。既有单次claim、unknown不重发、ACK+budget intent及Receipt回读保留。
- 复审：无公共状态枚举改造，无新迁移/表/HTTP/Provider调用。无页面改动，本波browser不适用。代码头迁移未改变，不声称当前真实库已到代码head。

## 验证

- 新测试首次写入命令cwd路径重复，FileNotFoundError，文件未写入；首次pytest因此无测试可跑，不能算RED。修正路径后实际RED：/tmp/aos-gn-red.log，7 failed/4.53s，退出1。
- 第一5组：/tmp/aos-gn-first.log，47 passed/2 failed/6.53s，退出1；旧来源fixture缺agent_run_id/skill_binding_id，补测试字段及审批前参数化，不降低生产校验。
- 第二5组：/tmp/aos-gn-second.log，51 passed/6.84s，退出0。后来新增测试命令又有cwd重复且未写入，修正后重新加入并运行；不将该轮51当新增用例证据。
- 累计13组：/tmp/aos-gn-regression.log，120 passed/90.79s，退出0。命令（services/aos-api）：

```sh
.venv/bin/python -m pytest tests/extension_runtime/test_ecommerce_content_pre_capacity.py tests/extension_runtime/test_ecommerce_content_capacity_owner.py tests/extension_runtime/test_ecommerce_content_budget_command_owner.py tests/aip/test_content_first_action_binding.py tests/aip/test_content_first_action_binding_pg.py tests/extension_runtime/test_ecommerce_content_repair_action_binding.py tests/aip/test_content_budget_risk_bound_pg.py tests/aip/test_content_first_action_budget_pg.py tests/aip/test_budget_configuration_runtime_pg.py tests/aip/test_aip3_action_control.py tests/aip/test_aip3b_action_execution.py tests/aip/test_aip_network_policy_action_producer.py tests/aip/test_aip7_agent_run_transition.py -q
```

- 最后补批准到期回滚测试：`.venv/bin/python -m pytest tests/aip/test_content_first_action_binding_pg.py tests/extension_runtime/test_ecommerce_content_pre_capacity.py -q`，/tmp/aos-gn-final-focused.log，22 passed/10.40s，退出0。不与120相加。9个Python文件compileall、git diff --check退出0；7条既有warnings。

## 证据边界与下一波 BG00GO

PG使用完整迁移的aos_test_*_ti4_test临时库，真实原ActionStore创建Draft/Approval、真实CapacityGate创建预约及跨连接可见性/外层回滚；正向来源和AgentRun转换明确使用替身，容量池为测试fixture，不是正式当前配置。新增事务测试证明容量提交边界，不证明自然AgentRun全链；来源准备单测也有权威reader替身。未直接INSERT批准或手填审批binding hash。

仍需完整合法Review/TaskRun/AgentRun/ModelRoute/Quota/Capacity来源→首生producer/checker→GE风险预算held联合证明，撤掉上述替身。优先从真实生产接口搭建隔离来源，缺producer则推进依赖；再接HTTP/原Action可读预览及browser，真实checker/当前实例独立恢复门后自然首链。八场景/观察发布未完成。Goal active，watchdog方案未部署，不push。

## 文件 SHA256
- services/aos-api/aos_api/ecommerce_content_budget_command_owner.py: `71b10bc63dd2f18bae9660a8d1156df63074d38bb349454a5b648b6a9b10d94c`
- services/aos-api/aos_api/ecommerce_content_first_action_binding.py: `94c80debd97dc4b71febe5592da8afb1f50366f194ea81981631321e8149de6a`
- services/aos-api/aos_api/ecommerce_content_capacity_owner.py: `521627cb25102c0d4e4f052b594057684ffc03893ef59b40e491dbc72eb9bf92`
- services/aos-api/aos_api/aip_budget_reservation_store.py: `f574f8b7799e96e83ea10e9826a8d031bc91c69f55736f018c86c1a38dd0eed0`
- services/aos-api/tests/aip/test_content_first_action_binding.py: `198c9b048b9a4e952ee7731ecb683668c4fb5bd99c5ba2dfa82e244a77bf76d9`
- services/aos-api/tests/aip/test_content_first_action_binding_pg.py: `d81892ba30a68a08257773d6a299954bd62bcfcd504ca12a12f0ade251293fb5`
- services/aos-api/tests/extension_runtime/test_ecommerce_content_pre_capacity.py: `5f7331674533659d4a9781f0fd112fb9615d6d89da0899ba03cc1367a69267ad`
- services/aos-api/tests/extension_runtime/test_ecommerce_content_capacity_owner.py: `8afc476cad51fffa968b2bb45bc6281c44bca198ab219afe4a46803d67870265`
- services/aos-api/tests/extension_runtime/test_ecommerce_content_budget_command_owner.py: `8636a7007a6707d623b6b8bce6633db5da5958e1b34a54d319730e256ae2d643`
