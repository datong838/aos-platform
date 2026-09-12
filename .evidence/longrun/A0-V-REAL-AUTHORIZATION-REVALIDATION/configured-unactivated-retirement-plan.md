# 已配置但未启用接入的安全卸载

基线 b5b25f80。e42 配置成功，启用 accepted 后因 Host 丢失，正式 disable 294359fc-4a51-4406-994f-bdc85e312881 已取消 enable 并 succeeded。现有 ar2_018 正常分支要求 detached cutover；a0v_019 仅无配置且无 enable/configure/disable 历史。因此真实无副作用失败安装无法恢复卸载。

新增 services/aos-api/alembic/versions/a0v_020_configured_unactivated_retirement.py（forward-only），tests/extension_runtime/test_configured_unactivated_retirement_pg.py，scripts/a0v_configured_retirement_acceptance.py。不修改历史迁移。不降低原 detached/never_enabled 分支。

新 configured_unactivated 回执仅允许：当前 active revision/CAS、单绑定 disabled+unknown+fenced/not enabled；所有控制操作终态、无 succeeded enable 及 enabled_committed 事件；无任何 cutover、dispatch binding、occurrence、execution attempt；至少一个资源且全部确认释放。必须有且仅有一个同代、当前 bindingRevision/epoch 的 succeeded disable 的 disabled_committed 事件，事件 payload 与 canonical SHA-256 匹配。配置非空且有对应不可变配置行，回执记录真实 configRef、disableOperationId、零激活接入/业务执行数量，不谎称无配置/无 enable 请求。

以现有 Installation lock + operation/resource 行锁防并发；现有数据库私有应用身份检查、终态一致性约束、回执 content hash 不变。新回执有 disable ID、无 activation ID。先专用完整克隆跑 upgrade 与逐场景事务回滚的正负案例；测试完整 InstallationService 卸载事务，裸函数回滚不冒充真正提交。负例覆盖未释放、未终结 enable、成功 enable 历史、配置错指针、错代/版本/租户、缺失/篡改禁用证明。克隆成功再主库迁移和正式卸载，原请求无成功回执可使用相同固定请求，不生成新键重试副作用未知任务。

克隆初版正例触发旧 disable_operation_id 对 dispatch_lifecycle 的第二外键。保持该外键不动，新增 unactivated_disable_operation_id（引用 runtime_operation），新类型旧 disable/activation 两列为空、独立列非空并匹配 authorityData；原两类型独立列为空。保留初版克隆供取证，重新从原 019 快照验证候选迁移，不修改主库。

重装沿用已签名 core/Niushop 1.3 + growth1.7，不再构建重复制品。scripts/a0v_ecommerce_1_7_first_install.py 新增 --after-config-recovery，先验证 e42 已正式卸载，再使用独立幂等前缀和 state/ecommerce-1.7-recovered-first-install.json；旧状态保留。scripts/a0v_ecommerce_1_7_configure.py 同名标志只读取该正式首装回执的新安装 ID，使用独立配置/命令文件及前缀，不覆盖 e42 历史。新安装 apply/verify 后先 configure，跨至少一次60秒续租再 enable，读取真实 Host/资源租约与回执，确认本轮修复。

持续观察脚本 scripts/a0v_ecommerce_continuity_observe.py 增加互斥 --after-config-recovery；配置 unknown 态仅在同一正式配置事件核验通过且三真实容器/租约有效时报告 CONFIGURED_FENCED_CONTINUITY，不报告 ready/enabled。旧观察模式保持原准入条件。
