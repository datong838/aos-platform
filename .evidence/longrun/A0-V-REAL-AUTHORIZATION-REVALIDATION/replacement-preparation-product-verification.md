# UQ6-D2e1 产品恢复替换计划入口

2026-09-14，基线32b98051。新增replacementPreparation.ts（只读安装/锁/发布签名版本/安装二次回读）和AssetBundlesPage入口。自动带入前驱exact ref与overlay，根资产固定原锁实际版本；更换单包版本保留其他根。身份/安装选择变化丢弃旧读取，身份变化禁止旧请求resolve。没有创建、审批、停用或启用调用。

真实浏览器发现旧Registry解析器遗漏spec.runtime与exports.knowledge，导致Niushop1.5接口200但版本详情拒绝。对照后端合同补只读声明结构，未知字段/非法路径仍拒绝；先RED再GREEN。新增步骤级固定错误提示，不把内部响应泄漏给用户。

验证：17项回归通过、类型检查通过；额外直接读取当前Registry服务公开Niushop1.5投影交给前端解析器成功。临时探测测试已移除，固定回归保留真实声明形状。

IAB实际点击当前97a…安装“准备恢复/替换计划”后进入组合预检：3根platform.ecommerce.niushop1.5.0、solution.ecommerce.growth1.7.0、solution.ecommerce.operations-base1.2.0；前驱revision5、lock a4441a…、overlay a0v-canonical-ecommerce-v1；解析按钮可用。未点击resolve，未产生新Lock或安装，当前Host和实例保留。

下一波D2e2核对1.8签名候选与本地Registry发布入口，形成包含实际UI能力的后继exact方案；旧审批不覆盖新锁。整体仍未完成真实业务首链。
