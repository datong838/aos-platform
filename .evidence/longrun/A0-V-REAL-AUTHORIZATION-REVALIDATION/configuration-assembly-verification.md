# D2c 当前四来源装配验证

基线45e6211f，m1串行，沿用A0-V主租约；AOS-000573权威不升级，230 L0挂起，不push。

实现位于aip_runtime_configuration_sources.py：输入精确职责计划和runtime policy引用，以原AIP当前权威派生data与budget revision；复用冻结、摘要、head、生命周期、有效期、network/egress与预算绑定校验。不持久化、不授权、不提交事务，调用者持有短事务。

## 验证

- test_configuration_assembly_pg.py + test_current_configuration_sources_pg.py：50 passed，7既有warning；包括真实隔离PG中的新policy引用指向过期/撤销/摘要错误依赖时拒绝，以及头变化、跨租户、特权连接、空/重复职责拒绝。
- 主库只读比对：configuration-assembly-live-proof.json，当前安装97aeb2e7-59ba-40f6-89a3-fb0293bc0497、generation 3a445eee-aa28-4459-9e5a-f12a806a94b1，装配结果与当前721433ba-5256-4b12-9043-0bcfab658bf0@1正文精确一致。
- 19类业务指纹不变；整个装配事务rollback。未调用append_configuration、configure、enable、Host或外部能力。

## 一致性与限制

符合D2c方案，未改既有脚本或运行状态。此函数仅校验来源，不证明职责人员有当前执行权限，不代替登记和configure/enable时原权限核验。当前输入仍是调用者提供的精确引用，产品来源选择和Host登记承接尚未实现。无独立审批身份凭空补入，真实首链/八工作台不据此计完成。

下一切片：审查原configuration store/service的单写者与Receipt合同，为产品登记入口定义exact目标、幂等和授权承接，再实施最小命令入口。
