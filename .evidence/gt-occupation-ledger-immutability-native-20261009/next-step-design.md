# 后续准入依赖与类型边界调查

原 Judge Intent 的事实为 inputDependency.state=awaiting_target_result，绑定真实 Target Intent/hash 与 expectedArtifact；不是可发出的完整 Judge input。prepared_call_occupation 已允许 target/judge purpose，但固定 input_hash 要求真实64位内容哈希。不得把 Target 原输入 hash 填作 Judge 尚不存在的运行输入，不补造结果、不抢先执行。

原物理合同 aip_physical_capacity_occupation_contracts.py 当前仅 PhysicalAccountGuardPreparation；Python准备入口 aip_physical_capacity_occupation.py 只包装 Source/guard/Model application，没有为新根/首事件提供严格非执行类型边界。下一可独立安全步骤是为服务端已验证原根/首事件增加严格 prepared_only 契约和响应一致性检查；executionAllowed和countsAsInflight必须是真bool false；根/事件callId、occupationHash、tenant和原xid/pid绑定一致，未知字段拒绝；只解析原窄SQL接口返回，不能让客户端对象授予权限。

拟改产品文件仅 services/aos-api/aos_api/aip_physical_capacity_occupation_contracts.py 和 aip_physical_capacity_occupation.py；测试 services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py（纯类型检查另按原测试布局登记）。先文件级方案与真实RED，再最小代码，专项/相邻和必要原生包装层验证。该前置不实现实际准入、Judge结果、费用authority或joint COMMIT；保留现有无条件拒绝门和默认迁移。完整业务首链继续依原方案真实证据。
