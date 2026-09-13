# BG-02 候选发现验证

基线3d1adf5c。当前策略/绑定/来源/原Claim/成功完成运行/最新调度控制关联，仅返回身份引用。运行时入口要求HostTransaction及当前aos_runtime租户GUC，分页after只是可回绕扫描键，不是消费ACK。

初轮8通过2失败，原因最小PG测试连接返回tuple而Host接口返回dict；修正测试row_factory后，与消费流程/PG共19项通过（7条既有依赖警告）。验证分页与回绕发现迟插入小key、最新续期control、更新代际后不能回退旧control、disabled/未完成/缺回执/来源hash/actor/tenant/generation排除，以及owner连接拒绝。SQL测试关系为临时最小表，不是完整授权验收；生产消费Owner仍全重验。

AR2-7扫描1882/分类168/迁移93，所有错误数组空；diff通过。无主库/启动/部署/push。下一项生命周期worker挂接，保持同一async循环和有界轮转，之后Occurrence到Run。
