# 下一恢复实施输入合同（未执行正式部署）

两个已登记候选：
1. 独立继任签名入口准备：新增sign_ecommerce_qyh_recovery_candidates.py及专项test，复用原Growth1.13资格验证/原signer，固定core1.4.3，其余三版保持；输入本Task actualbuild/qualification/hash。本步可安全离线实现；实际新正式签名与发布不是本Task授权。
2. 独立历史恢复HTTP入口准备：按qyh-durable-restoration-preparation-20261011/formal-implementation-plan.md，新增a0v_qyh_restored_http.py及tests；复用原正式release/有限LOGIN/外部OIDC门，不改现行preview的singleapproved/zero-binding规则。依赖独立唯一当前恢复安装对象、新配置/预算/current正式身份及连接切换批准；代码负门调查可独立进行，正式启动不得绕过依赖。

优先1，避免HTTP入口选择未签或沿用旧core coordinate。当前正式preview保留1.11签名/空安装事实；prepared159仍无ports/networknone，旧三个配置预算expired。不得把候选临时签名/8模块资格测试当正式安装或页面可用。
