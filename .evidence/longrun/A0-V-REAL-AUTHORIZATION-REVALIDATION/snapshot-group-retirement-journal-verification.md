### SC4-5h8 不可变清退准备验证

a0v048及PipelineSnapshotGroupRetirementJournal完成。新prepare须当前v2显式策略、原组input/候选命令和对象/候选投影合格，在原Audit回调保存exact audit、父commandHash、DB观察时间、完整条件tombstone与preparationHash；FK/SQL绑定、FORCE RLS、SELECT/INSERT only和不可变历史。每条清退重新验证原已出现行/规则完整引用、非wanted关系、旧时间不晚于原source，命令属性绑定manifest/assessment/audit/旧payload。

Store新增只读read_committed_link_retirement。清退前重放要求原Audit未变；清退已成功后按原Receipt的前置校验标记、当前tombstone和权威事件核验，不因旧边消失重造命令/检查点。空残留保存null，不造Receipt。已应用回读仍核当前v2及原行范围，不能删除wanted边。

61项Store回归通过4.76秒；14项完整隔离PG清退准备测试通过87.05秒。覆盖原命令清退后精确重放、缺记录read不写、回滚和后置撤权savepoint、旧边变更、普通删除Receipt冒充拒绝、v1拒绝、空残留、tenant/不可变、FK/assessment/count/active/time五类数据库反例，以及形状/hash合法但改成当前wanted边的准备被原Owner拒绝。

AR2扫描1924/187/93五类错误为空。主库仍未执行048或其他待升级迁移，主业务没有清退。下一波：独立提交确认后执行原条件清退及精确投影，验证commit ack丢失/图写入失败/撤权恢复；最后再次做完整关系残留核验，明确尚存数据缺口，再接业务Readiness/Fulfillment。
