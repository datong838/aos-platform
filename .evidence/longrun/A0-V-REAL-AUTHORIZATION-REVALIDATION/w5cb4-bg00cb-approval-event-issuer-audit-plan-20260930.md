# W5CB4 BG00cb｜网络批准事件签发与数据库身份只读审计方案

## 上位方案与当前门

复习 231/231-5 的真实审批、撤销、执行前复核与禁入合同，41 的 NetworkPolicy/Egress exact 有效期合同，及 BG00bz/ca 的 Event 版本与预检证据。当前权威 AOS-000929、m1 `49d0e4ff`、真实库 `aos_current_preview_20260927@a0v_117`；正式第二 checker、网络批准、八类配置和业务首链尚缺，Host/worker/Provider 关闭。

## 文件级范围

1. 只读查 `aip_network_policy_action_producer.py`、`aip_action_store.py`、`auth.py`、`tenant_scope.py`、`a0v_current_preview_http.py`、`aip3_001_action_control.py`、当前 PG 的角色/ACL/trigger，以及 231/41；核 API OIDC 检查与 DB Event 来源间能否建立不可伪造关联。
2. 不改代码、数据库、现有服务和真实身份。将可复核结果写入本目录 verification，续接 355 和 D-waves。若发现运行登录或 Event 表直写旁路，固定网络 ActionType 保持 a0v116 active DB 禁入，不用普通 GUC、请求字符串或自称签名替代来源证明。
3. 下一波文件级施工入口限定为：先隔离 test-only 证明最小受限 DB 登录可运行所需 API 读取与合法通用 Action；再设计仅固定网络 ActionType 的专用签发边界和正向 OIDC 链。任何真实库迁移另波按备份、第二全库克隆、零执行窗口办理。

## 验证/停线

验证代码路由、现行 API 登录角色、`aos_runtime` 表权限、Event trigger 与当前正租户网络 Event/Proposal 为 0；签名安装和 a0v117 preflight，8080/8434 页面与 18181 禁入。若 DB 或来源证据不能证明受控签发，本波仅审计结论，不放开 active，不宣称首链。保护所有既有 dirty 文件，m1 精确提交、不 push。
