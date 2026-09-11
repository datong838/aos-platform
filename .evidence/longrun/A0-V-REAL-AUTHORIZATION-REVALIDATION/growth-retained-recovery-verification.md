# 原正文恢复入口检查点

2026-09-11，基线0c54cf59。m1串行、不push、230 L0挂起。

- GrowthPlanDraftReceiver.recover不接外来answer，读取原scope SUCCEEDED attempt与exact私有正文，markings通过后调用既有receive重验原Run/Artifact/当前来源并保存或重放。无Provider调用代码路径。
- 读取与接收采用独立连接；正文append-only且接收重核hash，来源变化仍由receive拒绝。原来源已失效时已保存草稿回读仍是原Receipt，不新授权执行。
- Red：两个实际DB恢复测试因recover不存在失败；Green：23 tests passed，exit0，包含012一次性DB中丢弃外部原答复、全新Receiver实例/连接恢复及重放；无正文拒绝，unknown/failed/prepared/invoking均拒绝。
- 测试是合成图+新对象/连接恢复，不是实际OS断电/进程kill验收；未调用Provider，未运行实际经营链。主库仍未部署012、未重启API、未启用业务retention。
- 下一波：备份后按正式迁移流程部署012，实际D03生成组合接固定prompt+retention+接收/恢复；审批时当前来源重验仍必须补齐。源/安装/Binding就绪后才转真实首链和8场景。
