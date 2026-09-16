# Y3c-1a 原十二控制的保存输入续期差异合同

验收：Red为新模块不存在；最终/tmp/aos-saved-renewal-contract-final.log记录76 passed/3.34秒（新续期合同及原控制合同），git diff --check通过。实现只新增纯函数和测试，无运行器/路由/主库变更，无源调用。审查确认旧单路模型/权限合同未改，原与新窗口分别按24小时限制，业务字段与记录hash重验。下一波C1b/C2必须把原观察窗口证明、当前权限、完整input和saved-only围栏落实到不可变Receipt及正式Owner，不能把本次纯测试当成恢复完成。

实现补充：除字段重验外，逐控制复用原build_control_payload重算contentHash；立即后继须previous_hash等于原控制hash。跨多代后继仍必须由后续数据库Owner读取完整不可变链，本纯合同不声称证明未提供的中间记录。原/新组各自的共同窗口必须非空，新窗口可在原窗口之后而不重叠。

本波先实现纯语义差异校验，不产生恢复权限、不读源、不写任何持久记录。依照Y3c主方案，后续正式RecoveryOwner必须先由原数据库Owner读取并核验不可变控制、原完整input、claim及定义，再调用本合同；单凭调用成功不得执行恢复。

新增services/aos-api/aos_api/pipeline_snapshot_group_recovery_contracts.py和services/aos-api/tests/test_pipeline_snapshot_group_recovery_contracts.py。函数validate_saved_group_control_renewal(original,current)只接受两组各12个精确RuntimeControlRecord，以canonical pipeline匹配，不依赖调用方顺序；返回None或拒绝。

每对必须保留控制family、executor、source selection family；新control与selection revision必须严格递增，expiresAt严格延后、notBefore不早于原起点。只允许draft中的not_before、expires_at和source_selection_ref改变；maxSourceCalls、rowLimit、timeout、租户、installation/generation/epoch/config/package/source config/schema/masking/graph/mapping及全部其他字段完全相同。原/新draft均重新用原模型校验，单窗口最长24小时不可扩大。两组分别必须有十二canonical pipeline、唯一control和selection身份，并且原组的租户/安装/代次/epoch/config/package/source/schema/masking共同权威一致；不接受跨租户拼组。所有控制/selection引用由原_ref_identity检查类型与规范UUID。

设计纠正：原草案要求保留notBefore会与原模型24小时上限共同阻止隔日恢复，因此在编码前改为分离“原观察窗口”和“新执行窗口”。本合同允许新起点后移；C2/C3必须证明输入时间属于原窗口，当前执行属于新窗口，不允许用新窗口重写历史或将新旧窗口合成长窗口。两个组各自的十二控制必须有非空共同窗口，但两组之间不要求重叠。正式RecoveryReceipt当前定义必须有saved-only领取围栏，恢复后重新开周期须独立正式配置启用/审批，不能由续期自动获得新源读取资格。

测试先Red，覆盖正向乱序/隔日新窗口、空/缺/重复/跨租户组、不同控制family、selection family、actor、旧revision、相同/缩短到期、起点前移/超过24小时/无共同窗口、预算/限制/图与源配置漂移。此纯合同不判断当前时钟/当前角色、不声称验证签名或读取过数据库；这些必须由C1b/C2每事务正式Owner负责。旧单路合同与功能不修改。

下一波C1b不可变、租户隔离的RecoveryReceipt存储和原/新定义关联约束，C2正式授权Owner及产品API，C3保存恢复执行、C4组Run原子恢复、C5整链验收。m1串行、不push、230L0挂起，主库保持061。
