# 栖月汇当前库技术登记连接接入

已实施方案的候选A，当前库仅新增 qyh_restored_stage_login_20261011 专用 LOGIN 和精确账户 SCRAM HBA 行。原 a0v_159、权威命名卷、栖月汇 org-org/dev-project、原账户与权限保持不变。该角色仅属于 aos_configuration_stage_api，原 verify_identity 完整核验通过；没有新增业务用户、Owner 或 publisher。

先完成最新全库 custom dump 与无密码 globals 备份，分别两份校验一致、私密0600。新建角色前后的647表及六类原角色/ACL/owner/function元数据一致。独立回读另外与上一波完整恢复演练的647表数据比较，全部一致。38个原非pg角色保留，新增一个技术角色共39个。文件和凭据仅保存在本Task private/stage-transport-current，不进入Git。

原 configuration_stage_connection 实际连当前18446库；query/lookup的不存在目标返回NULL，无密码连接拒绝。dev-org canary、直接stage/config表、Host函数均真实42501。HBA实际读取为API账户SCRAM、新登记账户SCRAM、IPv4/IPv6全部reject，原本地维护规则保留；仅reload，未重启PG/API/Web，API鉴权GET与Web均200。

检查器首次在写intent前因错误健康地址404退出，无外部修改；修正为原公开OIDC端点和核准表名后再执行。独立回读首次误用了更早的注册维护前快照，判定不适用，改与上一波完整演练比较；没有修改数据来匹配旧快照。执行入口所有已有intent均拒绝重放。

方案与代码复核：维护入口绑定精确container/cluster/DB/migration/volume/loopback端口、旧HBA精确字节和上一波元数据。秘密只经stdin和私密文件，没有命令参数/日志口令。原Source写权限未撤销，不影响既有AIP路径。备份及两次647表回读、实际接口正负门为本波验证，不是仅mock单测。

限制：技术登记连接尚未注入正在运行的管理只读API，页面submissionConfigured仍false；Source Writer隔离、正式独立发布身份、当前预算和八工作台真实恢复仍未完成。仅可继续受控接线，不能将此凭据视作Host/worker/Provider或业务执行授权。Goal及完整恢复Task继续ACTIVE。
