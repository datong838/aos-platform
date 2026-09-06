# AR1-c 配置持久消费检查点

2026-09-06；基线m1@156f9944/AOS-000542，主Lease继续。

begin_configuration锁Installation→operation→binding，复核当前ETag、CAS、accepted不可变配置目标及当前权限/引用，原validating和fence同事务；ConfigurationConsumer使用独立空闲运行角色连接，claim提交、begin提交后才排空/配置提交。fencing重试不重复禁入，终态只确认事件，非可恢复中间态有界延后。无新HTTP、后台循环或第二份配置权威。

12项begin及6项consumer初始Red，联合原commit专项35passed11.75s。真实签名安装/专用OCI联合替换手动阶段推进：另一连接观察已提交fence；命名排空条件False拒绝后保留fence；True重试完成配置后注入ACK SQL回滚，fresh消费者禁止再次授权/排空仍可确认原终态，configRef/epoch/revision不变。初次测试接线把outbox当作直接有operation_id列导致1失败，修正为原event关联后1passed17.89s。最终安全累计894passed、6既有warnings、130.21s、exit0。既有JDBC退出日志流错误非本段逻辑，未扩大修改。git diff --check通过。

Prime只读初审及实际联合增量复审均无新增实质问题，确认完整state相等断言防重复配置/epoch推进。本段无页面改动，不称新浏览器验收。隔离18432临时schema/专用OCI，无共享迁移、真实业务写、Provider、费用或发布。正式角色/数据/策略及排空仍命名测试引用，业务场景0；AR1-c整波未完成，历史44/81口径不变。

下一段接入原AIP预算配置reader到真实隔离签名生命周期组合，并验证当前预算撤销不重新开放；随后其他正式引用、broker/费用及完整卸载重装。
