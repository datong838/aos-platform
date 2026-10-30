# G7-M｜后台处理配置条件预览方案 r1

时间：2026-10-31（北京时间）

## 业务问题

当前统一运营驾驶舱可以读取后台处理状态，也可以由用户点击“配置后台处理”。但正式命令会在当前客户后台身份、受保护保存位置或精确凭据版本缺失时直接失败。用户在点击前看不到一个可审阅、无副作用且使用业务语言表达的配置对象，因此无法判断本次配置具体是否具备条件。

本波新增纯只读的“配置条件预览”。它不创建身份、不保存配置、不写数据库、不申请 token、不启动 Host/worker/Provider；它只把现有正式准入条件转换成用户可判断的业务检查项。

## Rules

1. 当前正向范围固定为 `org-org/dev-project`，安装身份只由服务端当前正式目录派生，客户端不得传入。
2. 预览只允许 GET；拒绝 query/body 注入，不带幂等键，不产生 Receipt。
3. 凭据只调用 `exists` 探测精确版本是否存在，禁止 `read`、token 交换、正文回显和错误细节泄露。
4. 公开响应只出现业务语言：当前客户安装、后台业务身份、受保护保存位置、身份凭据；禁止 installationId、revision、etag、lockHash、secretVersion、locator、路径和原始错误码。
5. 只有四项配置前置全部通过时，`approvalAllowed=true`；这只表示用户可以批准“保存配置”，绝不表示可以处理业务。
6. 前端必须先展示预览；条件未齐时不显示配置确认按钮。条件齐备时仍需用户第二次明确点击，页面加载和预览都不得自动 POST。
7. 未知 POST 结果继续禁止自动重发；配置成功仍固定 `canProcessBusinessTasks=false`。

## 公开业务合同

新增：

`GET /v1/ecommerce-workshop/background-processing/configuration-preview`

响应：

- `status`: `reviewable | needs_input`
- `title`: “后台处理配置可以确认”或“后台处理配置条件未齐”
- `summary`: 说明本次只保存配置，不会启动业务处理
- `approvalAllowed`: 四项配置前置是否全部通过
- `checks`: 固定四项业务检查，逐项为“已具备 / 待补充”及可读说明
- `nextActions`: 下一步业务动作；不得包含内部变量名或错误码
- `sideEffects`: 明确数据库写入、配置写入、token 请求、业务处理、外部效果均为 false
- `canProcessBusinessTasks`: 固定 false
- `evaluatedAt`: 本次只读核验时间

## 服务端核验顺序

1. 当前客户安装：当前 operations 安装能由签名安装权威读取且 current/active 一致。
2. 后台业务身份：非秘密 OIDC 坐标完整且满足 external-only、dev auth off。
3. 受保护保存位置：配置路径为绝对路径，父目录存在、为目录且不可被 group/world 写入。
4. 身份凭据：用由当前签名安装与非秘密身份坐标共同构造的目标文档计算 locator，仅调用安全凭据后端 `exists`。

每项异常只转成稳定业务结果，不向客户端返回内部原因。检查之间尽量独立；后置检查依赖前置材料时显示“等待前置条件”，不得误报通过。

## 前端交互

- 后台处理未配置时，主按钮为“检查配置条件”。
- 点击后只 GET 预览并显示四项检查。
- `approvalAllowed=false`：显示下一步待补条件，不出现配置确认按钮。
- `approvalAllowed=true`：显示“确认配置（不会启动业务）”；只有再次点击才沿用既有 POST 配置合同。
- 状态或预览读取失败只影响后台处理卡片，不清空运营驾驶舱；提示“当前不会自动处理业务”。

## 修改目录

后端：

- `services/aos-api/aos_api/aip_route_worker_customer_lifecycle.py`
- `services/aos-api/aos_api/aip_route_worker_customer_lifecycle_wiring.py`
- `services/aos-api/aos_api/aip_route_worker_installation.py`
- `services/aos-api/aos_api/aip_route_worker_installation_authority.py`
- `services/aos-api/aos_api/routers/ecommerce_workshop.py`
- `services/aos-api/tests/aip/test_aip_route_worker_configuration_preview.py`
- `services/aos-api/tests/test_ecommerce_workshop_route_worker_lifecycle_api.py`
- `services/aos-api/tests/test_ecommerce_workshop_read_http.py`

前端：

- `apps/web/src/api/ecommerceWorkshop/contracts.ts`
- `apps/web/src/api/ecommerceWorkshop/parser.ts`
- `apps/web/src/api/ecommerceWorkshop/client.ts`
- `apps/web/src/api/ecommerceWorkshop/client.test.ts`
- `apps/web/src/components/workshop/OperationsPage.tsx`
- `apps/web/src/components/workshop/OperationsPage.test.tsx`

明确不修改 `apps/web/src/styles/45-ecommerce-workshop.css`，保护当前已有样式改动与 Lease。

## RED / GREEN

RED：

- 当前不存在只读配置预览合同；
- 未齐条件仍显示配置确认按钮；
- 预览读取 secret 正文、产生数据库写入或暴露内部坐标；
- 页面加载或预览自动触发 POST。

GREEN：

- 后端四项检查可独立证明通过/待补，响应严格拒绝多余字段；
- 缺身份、缺路径、缺凭据和签名安装漂移均返回 200 `needs_input`，不变成用户不可判断的 503；
- 四项齐备返回 `reviewable`，但所有副作用标志及 `canProcessBusinessTasks` 仍为 false；
- 前端必须“检查 → 展示 → 再确认”，未知结果不重发；
- 后端专项、HTTP 范围、前端 parser/client/component、相邻回归和类型检查通过。

## 验收与风险

本波完成只代表配置批准对象可审阅，不代表当前用户已经批准、配置已经写入、预算已启用或自然业务首链已经开始。当前业务库仍只读，Host/worker/Provider 保持 OFF；真实阶段数字不变。
