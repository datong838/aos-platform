# G7-M｜后台机器身份配置前置结果 r4

时间：2026-10-31 02:27（北京时间）

## 业务结果

`org-org/dev-project` 的后台处理配置前置已准备完成。正式页面现在可以向用户表达“后台处理配置可以确认”，但当前只具备保存配置的条件，尚未保存配置、尚未启动后台处理，也没有处理任何业务。

## 已成立的条件

- 当前客户安装：通过。
- 后台业务身份：独立的 `aos-route-worker` service account 已建立。
- 受保护保存位置：通过，目标配置文件仍不存在。
- 身份凭据：精确版本已写入 macOS Keychain；证据只验证存在，不记录 secret。
- 产品真实验证：使用产品 `RouteWorkerIdentityProvider` 完成一次 client credentials、JWKS 签名、300 秒时效、subject、audience、客户、项目和 `aos_route_worker` 角色验证。

## 过程修正与回滚

1. 首次钥匙串写入在二次确认处未完成；只读确认凭据不存在后，精确删除该次新增 client 与 role，恢复三项缺失。
2. 用随机合成秘密验证无回显钥匙串交互器的“写入、存在、删除、恢复缺失”全链后，才开启新的正式创建事务。
3. 首次产品令牌因身份容器比宿主快约 3 秒，被严格时钟校验拒绝；采用产品既有允许上限 5 秒，不放宽签名、受众、主体或租户校验。
4. 诊断发现 service-account 用户已有业务角色，但 `fullScopeAllowed=false` 时角色未进入 token；仅增加 `aos_route_worker` client realm scope mapping，保持全量角色范围关闭。

## 正式运行验证

- 正式 API：PID `11411`，`127.0.0.1:18080`，OpenAPI 200。
- Web：PID `4054`，`127.0.0.1:18434`，未重启。
- 影子 API：已关闭，`18081` 无监听。
- 配置预览：HTTP 200，四项检查全部通过，`approvalAllowed=true`。
- 未登录配置预览：HTTP 401。
- `canProcessBusinessTasks=false`。
- 配置写入、数据库写入、token request、业务处理、外部效果：均为 false。
- 目标配置文件：不存在。
- Host/worker/Provider/数据库迁移：OFF。

## 验收边界

本轮只解除“无法向用户展示真实配置条件”的工程缺口。下一步必须由用户在页面明确确认后，才允许保存后台处理配置；保存配置仍不等于启动业务，更不等于真实经营首链或八阶段业务验收完成。因此八阶段与工程闭合数字均不因本轮前置而增加。
