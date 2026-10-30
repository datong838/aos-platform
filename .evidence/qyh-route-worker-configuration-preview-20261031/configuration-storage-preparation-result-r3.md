# G7-M｜后台处理受保护保存位置准备结果 r3

时间：2026-10-31 02:16（北京时间）

## 业务结果

正式后台处理配置预览已从“一项通过、三项待补”推进为“两项通过、两项待补”：当前客户安装和受保护保存位置通过；后台业务身份和身份凭据仍待补。最终配置确认继续禁入，系统仍不能处理业务。

## 实施事实

- 使用既有私有运行目录，其归当前用户所有，权限为 `0700`。
- 正式 API 增加一项非秘密绝对目标路径；目标 `route-worker-identity.json` 在本轮前后均不存在。
- 没有创建空文件、占位配置、身份文档、OIDC client 或 Keychain 条目。
- 没有设置或猜测 client id、service subject、secret version。
- 影子 API 先验证精确预期，再切换正式 API 至 PID 8459；Web PID 4054 未重启，影子端口 18081 已关闭。
- OpenAPI 仍只暴露 GET，未登录预览仍返回 401。
- 只读预览精确得到：当前客户安装=true、后台业务身份=false、受保护保存位置=true、身份凭据=false。
- 数据库写入、配置写入、token 请求、业务处理、外部效果均为 false；`canProcessBusinessTasks=false`。

## 方案一致性与风险

实施与 `configuration-prerequisite-preparation-plan-r3.md` 一致，没有修改产品代码、数据库、Web、OIDC、Keychain 或签名安装数据。Host、worker、Provider、迁移继续关闭。

当前最短硬缺口是真实机器 OIDC 客户及其受保护凭据。不能仅填写格式正确的 client id/subject/version 来让界面变绿；必须有真实 IdP 对象和对应精确 Keychain 条目。该身份形成属于后续安全配置，不在本轮伪造或代签。
