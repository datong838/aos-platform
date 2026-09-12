# 已提交 preparation 的恢复与 Schema 实证

2026-09-12。安装 3d267738-ba0a-49ef-812b-d6b72d3374fd 已 applied@4，apply a24af9ea-e390-4292-94fc-531890c6bf1a succeeded；verify b440f801-7825-420b-8b48-38a054c96131 accepted。独立 Host 在 verify 报 LookupError 后关闭；三资源 released/observed=true、无绑定。extension_schema_installation 为空，现有 require_installed 对缺失回执抛出 LookupError。不能将安装或测试标为 active。

下一波六步：

1. 读取签名包 Schema requirement/compatibility，核对平台迁移祖先和 requiredRelations 的真实存在；通过已有 schema_registry.apply_once 维护入口登记 exact Receipt，回放不写，不伪造 migration 完成。
2. 产品恢复契约：applied 但没有绑定且全部资源已释放时，允许当前授权控制者通过幂等命令追加 preparation reset 到 approved；在同一事务终结尚未提交的 verify。保留原 succeeded apply、immutable 安装修订及资源记录。禁止重开原资源身份或重写原 apply。
3. 完善方案后增加不可变 revision transition、独立 evidence 类型、当前权限/CAS/资源清洁/未决操作检查。跨租户、绑定存在、不确定释放、verify 已提交均拒绝。
4. 真实隔离库执行一次 reset，重复命令回放，然后新 apply 使用新的 Operation 和资源 generation。
5. 同一独立 Host 完成 apply/verify，确认 active/ready、配置前 disabled/fenced。
6. 归档并进入四来源配置、enable 与经营首链。

风险：旧 PreparationOwner 只有最多 300 秒寿命，恢复不等于长期持续可运行；enable 后宿主持续性仍需单独观察与改进。严格保持真实业务目标，不能因安装过绿而宣称八工作台已完成。
