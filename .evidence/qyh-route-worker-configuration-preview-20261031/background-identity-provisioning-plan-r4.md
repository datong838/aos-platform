# G7-M｜当前客户后台机器身份配置方案 r4

时间：2026-10-31（北京时间）

## 业务目标

为 `org-org/dev-project` 新建一份独立、短期、可撤销的后台机器身份，让配置预览能够真实证明“后台业务身份”和“身份凭据”存在。该身份只完成配置前置，不保存后台配置文件、不启动 Host/worker/Provider、不处理业务，也不替代用户对最终配置和后续业务执行的批准。

## 当前事实

- 当前本地 IdP 为 loopback Keycloak realm `qyh-local`，公开发现文档返回 200，支持 `client_credentials`，JWKS 可用。
- 现有 `aos-api` human client 使用 audience `aos-api`、租户声明和 realm roles。
- 当前没有 `aos-route-worker` client，没有 realm role `aos_route_worker`，macOS Keychain service `com.aos.oidc.route-worker` 下没有条目。
- 当前客户安装和受保护保存位置已通过；后台业务身份和身份凭据待补。

## 身份合同

1. client id 固定 `aos-route-worker`，confidential、service account only；关闭 standard flow、direct access grant 和 implicit flow。
2. access token 生命周期固定 300 秒，不发 refresh token。
3. audience 固定 `aos-api`。
4. token 硬编码精确 `org_id=org-org`、`project_id=dev-project`。
5. service account 只授 realm role `aos_route_worker`；不授 admin、developer 或其他业务角色。
6. expected subject 使用 Keycloak 生成的 service-account user ID，禁止猜测用户名代替 `sub`。
7. secret version 固定 `v1`；Keychain service/account 固定：
   - service：`com.aos.oidc.route-worker`
   - account：`org-org/dev-project/aos-route-worker/client-secret/v1`

## 秘密与执行边界

- Keycloak admin 密码只在原容器内部由现有环境引用，不输出到宿主。
- client secret 只从 `kcadm` 的私有 stdout 管道进入一次宿主进程内存，再经无回显 PTY 写入 Keychain。
- secret 不进入命令行参数、环境变量、临时文件、Git、证据、日志或最终输出。
- Keychain 写入后只调用不返回正文的 `exists`；真实验收仅由产品 `RouteWorkerIdentityProvider` 读取一次，并只输出 PASS/失败类别，不输出 token、secret 或完整 subject。
- 不修改 human `aos-api` client、现有用户、数据库、Web 或签名安装。

## 执行与回滚

1. 再次确认 client、role、Keychain 条目均缺失；任一已存在则停止创建并只读对账。
2. 创建 realm role、service client、audience/tenant claim mapper和 service-account role mapping。
3. 获取生成的 service-account user ID 与 client secret；secret 立即写入 Keychain。
4. 使用产品身份提供器执行一次真实 client_credentials、JWKS 验签、subject/audience/tenant/role/TTL 核验；不进入任何业务处理。
5. 影子 API 加载非秘密身份坐标和既有受保护保存路径，预览必须四项全通过但所有副作用仍为 false。
6. 正式 API 单实例切换，Web 和 PostgreSQL 不动；影子验证后关闭。
7. 在最终配置命令未由用户明确触发前，目标身份文档文件继续不存在。

若步骤 2–5 任一步失败：删除本轮 Keychain 条目、client 和本轮新建 role，确认三者恢复缺失；不自动重试 token 或创建动作。若正式 API 切换失败：恢复上一 API 环境，保留已验证但未启用的机器身份用于只读对账，不启动业务。

## r4.1 钥匙串交互修正

- 首次创建在 macOS Keychain 的二次密码确认处未完成；只读对账确认 Keychain 条目不存在，随后已精确删除该次新增 client 与 role，三项均恢复缺失。
- 修正后的无回显 PTY 必须识别 `retype password` 并再次写入同一内存秘密，同时持续排空 PTY 输出；超时终止必须有界，不能无限等待子进程。
- 正式身份重新创建前，先用随机合成秘密和独立临时 service/account 验证“写入、存在、不读取正文、删除、恢复缺失”全链；合成秘密不得进入输出。
- 只有合成验证通过且正式三项仍缺失，才允许进行一次新的正式创建；这不是对未知结果的重发，而是在回滚确认无效果后的新事务。

## r4.2 当前身份时钟容差

- 首次产品身份获取已明确收到 IdP 200，但严格验签因身份容器比宿主快约 3 秒而返回 `ImmatureSignatureError`；该令牌未进入任何业务处理。
- 正式 API 现有显式容差为 2 秒，低于已测当前偏差；产品代码允许的上限为 5 秒，且既有测试证明该容差不放宽签名、受众、主体或跨租户校验。
- 将本轮影子与正式 API 的 `AOS_OIDC_LEEWAY_SECONDS` 从 2 调整为 5，只容纳当前可测的本机容器时钟漂移；其他身份合同不变。
- 调整后允许重新获取一次短期令牌完成产品验证；若仍失败，不扩大容差、不跳过验签。

## r4.3 最小角色令牌作用域

- 诊断令牌已证明签名、时效、subject、audience、org/project 均正确，但 `aos_route_worker` 未进入 token；service-account 用户本身已有该角色。
- 原因是 client 明确保持 `fullScopeAllowed=false`，因此用户角色不会自动进入该 client 的令牌。
- 只把 realm role `aos_route_worker` 加入 `aos-route-worker` client 的 realm scope mapping；不改为 `fullScopeAllowed=true`，不加入其他角色。
- 该修正仍属于同一未启用身份事务；修正失败则删除本轮 Keychain、client 与 role，恢复三项缺失。

## 验收口径

- IdP client、service account、role、claims 与 300 秒 token 真实成立。
- Keychain 精确条目存在，secret 不泄露。
- 配置预览四项通过，`approvalAllowed=true`，但数据库写入、配置写入、token 请求、业务处理、外部效果全部为 false，`canProcessBusinessTasks=false`。
- 目标配置文件仍不存在；Host/worker/Provider/迁移保持 OFF。
- 该结果只表示“可以请用户确认保存配置”，不等于用户已确认，更不等于业务首链验收。
