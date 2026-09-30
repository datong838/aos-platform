# BG00EV 私有消费者客户端方案

AOS-001010/m1@e2ead714。沿BG00EU产品接线缺口，复习231首链边界、BG00EM原actor/幂等Receipt及BG00EP Unix帧/peer军规。新增aos_api/aip_network_consumer_client.py及tests/aip/test_network_consumer_client.py，不改业务服务/DB/HTTP路由。

Endpoint仅绝对socket路径、api_uid、consumer_uid、ipc_gid；精确类型/正数/不同UID，当前euid必须api_uid。连接前parent0750/socket0660且owner/group=consumer，非symlink。connect 5s，内核getpeereid复用现有helper，服务端uid/gid精确匹配后才序列化发送JWT。无数据库凭据/API请求自报角色。

只接受精确Command或Inquiry，方法由类型确定；序列化JWT仅进内存wire，不落日志/异常。单次sendall 5s，响应复用5s整帧deadline/64KiB。响应strict JSON/重复键/NaN/schema1，unresolved/conflict/blocked固定shape；observed Receipt exactkeys/type/Proposal/Event/contentHash绑定。响应是历史Receipt证据，不宣称当前生效。发送后任一传输/协议异常统一unresolved，绝不重连或重发；发送前身份/路径不合法固定Blocked。只读查询必须显式传Inquiry，不自动执行。

测试使用真实socketpair验证实际帧/secret序列化/响应校验/丢响应单发送；这些是传输合同，不是正式OS或业务验收。真实kernel peer负例、真实同UID拒绝/不发token；正式不同UID正向部署仍独立门，不能用mock身份宣布通过。客户端不持久记录业务attempt，服务端已有持久幂等；产品层后续须冻结unknown直到只读对账，当前不暴露HTTP/自动重试。

RED→最小实现→专项及相邻回归→复审verification→精确m1提交→AOS/Prime。真实库118只读、119–122未部署、不启正式Host/worker/Provider、不读商城源/旧Run/manual run_definition、不push，230 L0挂起。
