# Y3c-2c 原保存输入原子续期Owner

## 实施与验证

2026-09-16实现并隔离验证：初始Red缺模块；首轮暴露原Run初建executor字段未设置，按原Completion合同修正。15项Owner/历史输入/围栏组合117.37秒通过；最终加入当前精确映射对原outputRows对象类型检查后，10项Owner完整回归79.75秒通过。日志`/tmp/aos-atomic-renewal-red.log`、`/tmp/aos-atomic-renewal-final.log`、`/tmp/aos-atomic-renewal-mapping-final.log`。diff检查通过。

覆盖实际十二selection/control/binding及definition/065 Receipt同事务成功、新连接原key重放、同key不同请求拒绝；第二次续期保留原input/原definition且接精确Recovery前驱；第十二控制失败全部回滚；审批末端原对象类型漂移亦全部回滚；原Completion锁忙立即冲突；过期/不推进窗口、错CAS、陌生manager、无input、混合/未停止失败Run及其他活动Run拒绝。全部停止失败的十二Run允许审批但仍保持failed，不伪装已恢复。正式恢复配置普通新领取仍拒绝。隔离源仅夹具一次（未知input例零次），无新Run/SourceClaim。

未完成项：HTTP/服务提交确认与回执查回、C3/C4执行、主库升级及真实首链。主库061/主服务不变，不push，230L0挂起。下一波C2d服务方案已另立文件。

实施审查补充：窗口不仅相对原控制，亦须相对当前前驱推进（新起点不倒退、终点严格延后），避免第二次续期缩回上一执行窗。原ScheduleClaim初建running行executor字段为空，使用原Completion相同running条件（未标记stopped且finished为空），依赖完整input和同key锁；不能错误要求完成后才填写的executor_id。failed仍须明确stopped=true及finished非空。

复习依据：Y3c双窗口主方案、C2锁序/权限方案、C1a差异合同、065原始回执存储、066 saved-only禁入、C2b历史核验。业务动作是续期并准备恢复原input，绝非补造历史组或新源读取。

新增文件services/aos-api/aos_api/pipeline_snapshot_group_recovery_owner.py、services/aos-api/tests/extension_runtime/test_snapshot_group_recovery_owner_pg.py。本波不改HTTP/工厂/主库，不运行Completion。后续再接服务接口及C3/C4运行。

参数只有scope、groupId、principal actor、expectedDefinitionRef、expectedRecoveryRef、inputManifestHash、UTC规范化的新窗口和幂等key；无任意draft/SQL/actor执行器输入。先runtime tenant检查，尝试原Completion相同advisory key事务锁，冲突立即busy；随后definition advisory、当前manager管理许可/安装锁、head、控制、schedule、Run。历史输入必须在任何append前由C2b核验。幂等命中原request返回历史Receipt且重验当前管理身份，不宣称当前可执行。

新请求CAS当前definition和原组最新RecoveryRef；当前定义不得retired，须保留原安装/代次/executor/cron/timezone/policy及同十二schedule/control family。最新binding必须仍为当前定义；原组必须十二running或十二已停止failed（混合、未知终止拒绝；已完成走未来只读结果入口）；所有成员schedule不得有另一活动/未知Run。新窗口当前有效且不超过24h，起点不早于原窗口，终点晚于原各成员窗口。原/当前executor仍须当前管理角色，后续每个原Selection/Control Owner重验实际执行权限。

服务端从原业务draft构造后继，前驱取当前definition精确控制/选择/绑定；各自原Owner append/bind。所有新增控制先由C1a与原控制比较，再由原PolicyOwner核验当前十二映射/权限/源/预算/policy。专用保存路径调用Definition._save，intent=renew_saved_group；同一事务写065 Receipt，并强制本波定义与恢复约束IMMEDIATE。内部key为包含scope/group/request/key/阶段/成员的确定摘要，不能互相串单。任何中途错误回滚全部十二续期，无commit、无源调用、无Run修改。

验证：原输入具名隔离准备；成功新连接读取回执/幂等重复零新增；晚成员注入失败零部分selection/control/binding/definition/Receipt；相同key不同request拒绝；无input、错CAS、过期窗口、manager/executor权限缺失、另一组busy无审批；恢复专用定义仍被普通新领取拒绝。后续C2d接口、C3双窗口恢复、C4原Run状态、C5完整恢复，再Y4–Y6/Z。
