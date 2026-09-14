# SC4-5f3 当前快照组边界

2026-09-14，基线7525f21f；Lease A0-V-SC4-CURRENT-SNAPSHOT-GROUP。

新增PipelineSnapshotGroupOwner，按exact control ID固定顺序嵌套原run_current_snapshot，验证同租户/安装/代次/epoch/config/package/source/sourceConfig/schema/masking/platform/shop；pipeline/table唯一，共同窗口与最小限额；同步Host回调后再核验所有原当前控制与完整组绑定。不发源读取、不认领、不签发权限令牌或Receipt。

初始缺模块红测；单元11通过、一个使用普通列表迭代器误作异步生成器的测试失败，改为真正生成器后与隔离PG共14 passed/7既有警告/4.34s。原_reject_deferred语义未修改。PG真实控制/选择历史两成员组合通过，中途追加当前控制导致拒绝并回滚，记录数保持2。签名资产门是明确fixture，未证明主安装当前资格。

AR2 1911/187/93五数组空；无迁移或业务主写入。当前组必须继续绑定认领和同事务观察输入，尚无组级持久化或正式Fulfillment。

SC4-5f3：当前快照组Owner边界完成，14项单元/隔离PG验证通过。固定顺序嵌套原控制/选择Owner、同租户安装包连接约束、共同窗口/最小限额、执行后完整复验；PG中途控制更新导致外层回滚。签名资产fixture未计主安装通过。下一组认领与持久化输入/共同观察证据，再关系质量与Fulfillment；主首链未完成。
