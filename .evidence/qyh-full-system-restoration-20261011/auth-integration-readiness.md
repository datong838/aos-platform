# 原登录复用与正式发布接入对账

当前只读恢复API18080实际GET /v1/auth/oidc与原Bearer dev /v1/me各两次稳定回读；同一恢复卷aos-qyh-history159-prepared-data-20261011，精确org-org/dev-project、栖月汇商贸有限公司、tokenKind=dev。无token发行、无发布尝试、无数据库写。

132原产品方案允许非生产Dev登录；现有管理登录可复用，并不需要企业OIDC才能查看恢复数据。接口jwksConfigured=true在原oidc.py非external-only分支固定为true；实际jwksUrls空、password grant未配置，只支持dev。因此该字段不能作为正式外部登录成功证据。auth.py固定Bearer dev的principal.subject为user:dev；asset_bundles.py发布actor取认证subject，原Registry要求publisher scope及发布者不同于创建/验证者。不能仅更换actor或用历史成员字符串完成独立身份认证。

r1只保存me响应字段名，未验证响应tenant；发现证据过弱后补充精确租户与名称断言，以r2为有效结果。补充时断言误放在me读取前导致UnboundLocalError，发生在纯GET阶段，修正顺序后两次真实读取通过。没有凭此错误重发写请求。两个结果均保留，最终源hash以r2为准。

复审：没有产品代码改变、没有覆盖旧登录配置/密钥、没有取消正式发布职责分离、没有把开发身份升级成Owner。135历史安装和原电商八模块复用主线保留。正式接入缺实际身份来源；八工作台实际可用仍未完成，完整恢复Task/Goal ACTIVE。下一步原正式登录接线与独立发布认证、原当前预算审批和新配置/安装，不启用关联未知旧执行的407历史实例。

旁线gt-native-freeze-lifecycle的既有check.log在intent之前显示docker exec126/openat input/output error，本轮只读重核同样126；无intent/result，未LOAD、未重启该lab、未冒充QYH库失败。当前恢复卷预检与HTTP读取正常，旁线故障不改变整体Goal。
