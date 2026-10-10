# Task10 原联合结束入口：精确约束选择调查

Rules：231/joint §11.3、产品baselinev3、AOS-001687，m1唯一writer。当前HEAD b53146d7c；Task10 receipt==Lease、owner明确、27 Lease无scope重叠；尚未Delivery。上一轮已交付操作闭包并只读核18已知候选事件；native RI合同与全joint仍缺。不无限扩大目录审计，本步验证真实结束入口必须面对的精确选择问题。

候选①完整约束收敛入口：约束名字究竟选择哪些目录对象、是否同时包含原unfinalized guard；②native安装可信合同/Source最终时限，依赖正式安装和WAL裁决。选择①只读证实条件，不执行SET CONSTRAINTS、不改变deny。

文件仅本Task证据：本方案、read-constraint-selection-r1-1687.py、constraint-selection-current-r1-1687.json、复审。沿18已知候选事件（不是完整闭包），用真实trigger事件掩码查pg_trigger.tgconstraint对应pg_constraint名字/schema/deferrability/类型/被引用关系。按schema+name反查全部对象，找名字碰撞与匹配范围扩张。明确属于原物理unfinalized guard与legacy RI，不能只凭trigger字母顺序选，也不能猜trigger name==constraint name。暂不生成执行SQL，不SET ALL/ALTER/disable/no-op/绕过guard，原库只读，不调用未知回调。

验收为真实目录可对账、精确hash绑定、匹配集合完整，不是最后提交或首链；Owner/ACL/批准Root、WAL截止等仍独立门。无产品修改，无UI改动不重复浏览器。调查若发现歧义/提前deny，登记为完整入口实现要求并继续安全设计，不将Goal blocked。

原调用源码复核发现候选种子不完整：原prepare_guarded_source_model_application调用prepare_capacity_occupation_account_guard，SQL写account_guard INSERT/ON CONFLICT UPDATE；parent debit写parent_debit_guard INSERT/UPDATE；原case/input/intent路径写case_input_binding INSERT。之前15seed+3effect仅已知子集，未宣full closure。保留r1，在r2加入这四种缺失事件并重新查询原目录；需要继续按原调用而非表清单补齐full Model/Judge与普通Content分支。不运行原test夹具（含drop teardown），不回放旧risk。
