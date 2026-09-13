# D2d-1 配置登记请求合同

基线df1804a8，m1原A0-V任务。新增configuration_stage_contracts.py和test_configuration_stage_contracts.py；31 passed、7既有warning，git diff --check通过。

合同固定stage-configuration动作，安装/代际UUID、etag/bindingRevision、原AIP职责和策略精确引用，可选配置上一版引用。拒绝客户端subject/tenant/deadline/权限/请求ID/自选data/budget/状态/任意payload，拒绝重复职责身份、非规范UUID、版本强制转换、嵌套model_copy绕验证。JSON正文有64KiB上限，职责1至64条。

仅为产品交接输入合同，尚无公开HTTP入口、队列或主库写入。未改现有configure/enable行为，未授任何权限。下一步D2d-2实现原Host中的原子登记及数据库交接表；必须确保配置记录与结果同事务，失败无部分登记；随后再做API受限身份与产品来源选择。
