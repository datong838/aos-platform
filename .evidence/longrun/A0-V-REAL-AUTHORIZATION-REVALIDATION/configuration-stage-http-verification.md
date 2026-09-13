# D2d-3b 受保护连接与HTTP验证

基线72cd9a69，2026-09-14，m1原A0-V任务。新增restricted_api_identity.py共享旧UI身份校验，旧UI入口/错误保持；新configuration_stage_connection仅使用独立凭据文件、严格LOGIN/NOINHERIT/单逻辑角色/无ADMIN/无特权连接。本地SQL适配在远程OpenFGA模式拒绝。

固定HTTP挂原bundle-runtime-installations：POST configuration-requests与GET configuration-requests/{request_id}，当前Principal与APPLY角色门，SQL再次核当前成员。固定DTO/no-store，错误不暴露SQL/DSN，缺凭据503，无Host/Web凭据兜底。服务在受限事务提交后返回成功，未知commit只抛出不重发。

验证：原UI连接15项回归通过；新连接真实隔离LOGIN身份、继承/额外角色/ADMIN拒绝、固定SQL服务收件与读取通过。首轮HTTP正例失败400，根因为JSON数组被严格tuple模型拒绝，修复数组容器适配后，新连接/HTTP/合同/原UI连接联合64 passed、7既有warning。旧HTTP/身份部署/配置目录另29项回归通过。router aggregate仍匹配550条，diff检查通过。

边界：未部署主库或重启API/Host，浏览器尚不能完成登记流程。SQL夹具为隔离schema原记录形状，不能当真实客户闭环。现GET仅按服务器requestId，响应丢失而未知ID时需下一切片按原请求键只读找回；在其完成前不声称未知结果恢复闭环。

下一波次D2d-3c：新增只读按原请求键找回的数据库与HTTP入口，仍核当前成员/安装标记，仅返回原scope+subject记录，查询不插入、不重复登记；然后继续来源选择UI与受控部署。
