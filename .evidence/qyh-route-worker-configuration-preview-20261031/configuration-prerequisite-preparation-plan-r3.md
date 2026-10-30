# G7-M｜后台处理受保护保存位置准备方案 r3

时间：2026-10-31（北京时间）

## 业务目标

在不创建后台身份、不写配置正文、不读取或新增凭据、不启动业务处理的前提下，先让当前正式 API 知道未来后台处理配置应保存到哪个受保护位置。完成后，“受保护保存位置”可以独立通过；后台业务身份和身份凭据继续保持待补，最终配置确认继续禁入。

## Rules

1. 使用现有私有运行目录 `.evidence/qyh-route-worker-configuration-preview-runtime-20261031/private/`；该目录当前归本用户所有且权限为 `0700`。
2. 目标只是一条绝对文件路径，文件本身保持不存在；不得预写空文件、占位 JSON、秘密或安装文档。
3. 只给正式 API 进程增加 `AOS_ROUTE_WORKER_IDENTITY_FILE`，其值指向该私有目录下的 `route-worker-identity.json`。
4. 不设置或猜测 `clientId`、subject、secret version；不调用 Keychain 写入，不请求 token。
5. 切换沿用单实例和回滚门：保留当前 Web，不动 PostgreSQL；新 API 监听成功并通过 OpenAPI、401 和只读预览后才停止影子。
6. 预览期望值固定为：当前客户安装=true、受保护保存位置=true、后台业务身份=false、身份凭据=false；全部副作用=false，`canProcessBusinessTasks=false`。
7. Host、worker、Provider、迁移与定时任务继续关闭；该准备不构成配置批准或业务验收。

## 变更范围

- 新增本方案与运行核验材料。
- 当前正式 API 运行环境新增一项非秘密绝对路径。
- 不修改产品代码、数据库、Web、OIDC、Keychain 或现有配置文件。

## 验收与回滚

- 目标父目录必须是目录、归当前用户所有且 group/world 不可写。
- 目标文件在本轮前后均不存在。
- 正式 API 启动后 OpenAPI 仍只有 GET，未登录预览仍 401。
- 只读预览必须精确得到两项通过、两项待补，且所有副作用为 false。
- 任一条件不符，恢复上一正式 API 环境，不创建目标文件。
