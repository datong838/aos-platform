# newJudge 原件依赖 Intent 验证记录

m1 390360ce / AOS-001607；已登记 atomic/Judge Scope，独立窗口 gt-newjudge-intent-native-20261009，原5436容器/命名卷/cluster身份核对一致。只追加原authority末尾，所有旧compiler字节保持一致；普通路径默认flag关闭。精确文件为 services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py、tests/aip/test_physical_capacity_occupation_pg.py、tests/aip/test_model_eval_judge_authority_pg.py，以及 atomic Task 的 source_newjudge_native_trial_1606.py。

实际验证：R1新增准备态正向后原全测试绝对批准期限到期，1FAILED68.40s，保留。R2隔离新增caller与原默认完整回归，1PASS79.01s；复审原Proposal/幂等字段错误路径为空，修正从已认证approvalSnapshot取原件且明确approval事件幂等键，加入非空原件一致断言；最终R3新数据库bc8172...原159 bootstrap/原C verifier/实际Source/SCRAM/newJudge独立parent，1PASS81.57s。默认原完整Judge新数据库f3c5...1PASS64.57s（源码原默认路径未变）；相邻293PASS0.70s，7既有warnings。默认runner第一轮清单顺序核对错误发生在attempt创建前；完整身份集合排序修正后通过，没有降低身份核对或重复未知效果。

Judge Intent 绑定原Target Intent同case/hash/Application/xid/pid、原newJudge申请及独立批准/Actor/Rule、原shared debit及费用三桶，状态明确 awaiting_target_result，精确重放相等，换Intent/Target/case/null以及private SELECT拒绝。Target测试allocation1minor只是合成批准风险额度，不是真实费用或价格；Judge10minor实际原case风险分配。没有伪造actual output。原deferred门的实际conn.commit返回23514，独立连接 pg_xact_status=aborted，Target/Judge/debit准备表0；Source1保留；account_guard1是原guard-race提交证据，版本匹配，未删除。独立catalog FORCE RLS/私有Owner/runtime无DML、immutable/禁止truncate/deferred拒绝3trigger核对；临时public entry卸除，occupation NOLOGIN/member0。此前全体原容器ID/StartedAt/mounts/ports逐项相同。

方案自洽性：新SQL不接默认migration、不授Provider/transport、不修改旧Target CHECK与安全流程；compiler prefix字节相同，AST及代码diffcheck通过。没有浏览器界面改动，浏览器验收不适用此隔离数据库实验。没有独立督导PASS声明。日志JWT样式计数0，未读取或输出私有密码。

局部验证GREEN不代表Model稳定收益、正式权限、真实Source部署、四腿完整COMMIT、自然首链或长期Goal完成。五父Task仍ACTIVE；只收口本次隔离窗口。后继已登记：全共同终结及Target真实结果晚绑定输入协议/物理累计竞争，不得将awaiting状态转成可执行输入或将未定费用当0。
