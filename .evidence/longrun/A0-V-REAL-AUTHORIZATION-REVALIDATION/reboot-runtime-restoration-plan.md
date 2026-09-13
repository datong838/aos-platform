# 栖月汇重启后受控运行恢复

基线aa3010c4。实际parent eda57424-b8cb-401e-a6f7-94220cb4f9ef active@5；23afd代次rev5/epoch4 disabled/fenced/unknown，3资源全released/observedRelease=true，P02旧计划disabled且unstopped=0，业务路由0。已有reset仅允许unbound applied，不能修改active历史或删除绑定来重用。

新增scripts/a0v_qyh_reboot_recovery.py固定本次目标与幂等前缀，持久化每个动作意图后才调用既有Owner。步骤：当前只读预检→精确disable取得前代drain Receipt→备份→同版本组合替换候选create/submit/approve→新runtime-apply→verify→现有配置/启用Owner重新配置新代。此脚本阶段先覆盖disable/create/prepare/verify和只读observe；配置/启用按新代确切ref另行冻结，不复制旧执行授权。

保留原父安装和旧数据/P01/P02/审批历史；前代禁用不改变其active安装基线供合法lineage引用。新候选只用core1.3/Niushop1.5/growth1.7/operations1.2既有签名包。不是新发布，不push，不触及230 L0。未知动作结果只observe不重发；同动作意图文件存在即阻止再次发起。主库仍025，不部署登记迁移。

仅专用固定脚本复用已有正式生命周期服务，不能视为无需开发者的产品恢复入口已完成；后续需将恢复编排变成产品能力，并验证计划/配置的精确迁移。新增tests/extension_runtime/test_qyh_reboot_recovery_guard.py验证当前快照漂移拒绝及意图不覆写，再执行真实恢复落回执。

实测补充：disable已成功bed965ec-c701-4514-92e9-41885b1d0353，既有Owner先fence递增一次、finish再递增一次，终态binding为rev7/epoch5。初稿误预计rev6，创建前检查已拒绝且尚未创建候选；按disable_commit.py现有两阶段契约更正固定检查为rev7，不重发disable，且仍需require_predecessor_drained核验真实事件。
