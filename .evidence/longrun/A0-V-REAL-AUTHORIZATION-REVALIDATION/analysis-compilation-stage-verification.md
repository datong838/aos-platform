# CF2-3 exact 阶段读取验证

基线999104f5。run_with_stage复用当前安装职责SourceOwner边界，以显式stage_ref读取当前head，校验租户、revision/hash、frozen/ready、L1 exact来源、模板正文hash、三阶段顺序及所需职责槽位，前后重读并拒绝deferred。无模板扫描、创建、冻结、权限写入。

Red缺run_with_stage，11 failed；Green阶段11+职责11+绑定11=33 passed，/tmp/cf2-stage-green.log。Store/角色Owner为具名替身，仅正式阶段请求合同与来源解析器真实，不宣称当前安装或PG阶段实体验收。AR2 1889/171/93全部错误为空，diff --check通过，memoryctl validate GREEN/AOS-000573。

下一波CF2-4核对D01/D02/D03当前绑定、Logic发布及分析意图覆盖；受安装约束的模板选择仍未实现，不能由调用者任意stage_ref授予执行权。之后CF3准备Task/Brief/Context与编译，CF4解除真实START已知失败，CF5候选安装，CF6真实业务。无主库部署/push，230 L0挂起。
