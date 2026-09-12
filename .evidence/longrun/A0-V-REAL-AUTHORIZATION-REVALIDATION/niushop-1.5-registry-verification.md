# Niushop1.5 本地 Registry 追加验收

2026-09-13 03:19；执行源码 eb30a342，构建源码 e957488c。新profile先红1项，再与既有1.4/1.7回归共13 passed，4.72秒。实际 preflight通过；19:17:30Z完成 NIUSHOP_1_5_REGISTRY_GREEN。

仅Niushop1.5 create/validate/publish各1次，其余core1.3/growth1.7/operations1.2均0变更。签名根12→13版本，新Niushop内容sha256:1a21beea3ed901baa95042636eca915eb7915709be24f2e58a2690f94005e7dd。执行后独立逐文件回读旧根所有文件在新根逐字节相同；旧12版本未改写。

备份4,778,880字节，sha256:3b9ff52a24b3dc7ef5229797831c5ef58c175f564aaa8e60a7135fe402eb39a9，独立重新计算相符。文件名沿用helper历史growth-1.5字样，实际备份为当前aos_meta_head。保留全部备份，私密env备份不入库。

.env根通过精确CAS从09-12的niushop1.4根切至09-13/state/niushop-1.5-registry/signed-bundles-niushop-1.5。API/Host现有进程没有热加载；当前安装仍Niushop1.4。安装记录总数7、正租户7、canary0均不变。回执target_versions字段属于旧helper固定历史growth1.5存在性检查，不可误当Niushop1.5计数；本次Niushop事实来自逐版本RegistryService回读和releases记录。

当前Host连续性再次通过，详见niushop-1.5-registry-host-continuity.json。本波没有安装变更、Provider或外部发布。当前Registry成功不等于商品真实链路成功。

下一波：按231-3复核当前实例替换/禁用/恢复规则；先做商品源schema的真实只读核验，再确定P02最小正式接入及当前安装切换方案，维持单写者、旧数据/Receipt保留，禁止直接改活跃lock或生成Case/Run绕过业务入口。
