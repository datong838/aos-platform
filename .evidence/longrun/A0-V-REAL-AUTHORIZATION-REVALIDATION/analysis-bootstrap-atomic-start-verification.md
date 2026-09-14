# SC4-3c4 专用原子暂停初始化

2026-09-14，基线ee7029f0。方案analysis-bootstrap-runtime-design.md。

专用_BootstrapProductionStartService在原事件事务和保存点内核验实际独立审批集合，经原ProductionStartService批准Plan/建TaskRun，再原start_run/pause_run保存首步not-started检查点。返回时唯一TaskRun/Task均paused、零Step/Artifact/AgentRun；原审批/来源/Preview继续有效。重放不建新Run；暂停前后失败全部回滚。

固定初始化Action采用R1独立审批专用策略；通用R1不变，普通ActionStore无当前守卫不可创建或审批，通用StartGate仍拒绝初始化；普通resume与外部Action租约/请求准备也拒绝复用初始化授权。后续业务续跑仍需专用当前权威，不把初始化审批当经营方案审批。

实际衔接修复：正式LogicPublicationStore只更新published_version，保留图头draft；原StartGate仅看published状态错误拒绝正式发布。现正式记录通过原Store校验snapshot/hash，匹配当前发布指针与请求版本，归档/删除/指针不符拒绝；无正式发布记录的历史图保留published兼容且核对版本。

验证：首次4项缺模块红测；实测发现正式发布检查差异后按上述权威修复；ResourceRef改用模型属性读取。普通恢复用例先复现未拒绝，再修复。外部租约加入明确初始化拒绝，独立测试executor为隔离fixture。最终八组累计61 passed，7既有警告，38.93秒（/tmp/a0v-bootstrap-start-final3.log），包括原analysis_run_resume_pg回归。AR2 1904/182/93错误为空；memory GREEN AOS-000573。

严格边界：角色、Action注册、来源及部分可用性为隔离fixture，独立审批是测试记录，不能用于主租户。无主安装变更、真实模型或经营步骤调用，不push，230 L0挂起。

下一SC4-4：把当前编译/预览/动作及暂停初始化接入正式事件START和审批等待/继续流程；原严格xfail在真实完整START证据前不移除。随后具备当前业务权威的续跑、新候选/主安装恢复、栖月汇真实首链、八场景与连续观察。当前不宣称完整业务目标完成。
