# D2d-5 配置登记结构真实部署

2026-09-14，执行器85a24464，独立迁移租约A0V-CONFIGURATION-STAGE-LOCAL-DEPLOYMENT-20260914。

真实主库备份5367271字节（0600）保留于私有configuration-stage-deployment，恢复至aos_configuration_stage_20260914_test，19项业务指纹一致后完成035→038克隆迁移。队列为空，FORCE RLS，runtime只有SELECT和五完成字段UPDATE，API无队列表权，4固定函数仅受限API可执行、PUBLIC/runtime不可执行。见clone-proof。

固定prepare证据和执行器哈希后，主库原基线再次一致，先写一次apply-intent再迁移。主库读回038、19项业务指纹不变，队列0；health接口ok。未创建业务请求/配置/审批，未变更Host或业务运行。见main-proof。2项部署保护测试通过（先RED后GREEN）；真正结构验证以恢复副本和主库回读为准。

下一波D2d-6：专用NOINHERIT LOGIN→aos_configuration_stage_api身份，仅执行固定函数，正租户/原subject只读查询、错subject/错租户/直接表访问拒绝。先克隆再主库，身份私有文件与证明摘要分离。API尚不加载提交身份，Host接管方案先于开放登记。
