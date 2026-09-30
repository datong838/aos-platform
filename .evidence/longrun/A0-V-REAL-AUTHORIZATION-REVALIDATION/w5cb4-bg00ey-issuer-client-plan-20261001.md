# BG00EY 独立签发客户端计划

基线 AOS-001013/m1@8dc4a624；复习231首链、406及既有issuer contracts/service/reconcile/IPC。Task W5CB4-BG00EY-20261001。当前真实库只读，不部署、不启Host/worker/Provider。

## 业务落点与最小改动
API最终必须通过独立签发者取得当前真实ApprovalEvent。既有签发者已经做OIDC、持久attempt、决定及独立只读对账；本波仅提供缺失的客户端，不复制审批权威，不将传输成功视为批准。

- aos_api/aip_private_service_transport.py：从consumer client提取既有路径权限、UID/GID、内核peer验证与单连接上下文；不发送业务数据。
- aos_api/aip_network_consumer_client.py：保持原Endpoint、错误和单发帧合同，仅使用共享连接。
- aos_api/aip_network_issuer_client.py：独立IssuerEndpoint；exact Command/Inquiry，一次decide_once/inquiry帧，复用帧读取。响应严格匹配既有schema/status/eventId/decision；observed只表示签发者对账结果，非激活。未知响应统一unresolved，无自动重连。
- tests/aip/test_network_issuer_client.py：真实socketpair帧/响应丢失、严格响应、内核peer拒绝；共享consumer回归。

## 顺序与验收
先RED缺模块，再最小实现；专项与consumer/issuer协议、服务、attempt相邻累计。无UI变更，浏览器不适用。真实socketpair不等于独立OS身份部署证明；peer正向及正式OIDC/数据库部署仍独立门。请求与事件精确绑定继续由既有issuer只读reconcile实现，客户端不另建数据库权威。API持久attempt与产品HTTP接线列下一波，不把裸客户端暴露成批准入口。

## 风险与回滚
共享连接提取必须保留消费者行为；先身份后JWT。响应丢失不重发；下一波产品层必须持久记录首次调用并只读对账。未改当前.env/服务/数据库；回滚仅本波文件，不覆盖用户其他改动。按verification、精确提交、Delivery/CAS/Prime、D-waves收口。
