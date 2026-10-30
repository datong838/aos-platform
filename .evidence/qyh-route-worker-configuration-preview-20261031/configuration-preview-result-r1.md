# G7-M｜后台处理配置条件预览结果 r1

时间：2026-10-31（北京时间）

## 结果

已按《configuration-preview-plan-r1.md》完成最小实现。统一运营驾驶舱在后台处理未配置时，不再直接提交配置，而是先读取并展示四项业务条件：当前客户安装、后台业务身份、受保护保存位置、身份凭据。只有四项全部通过，才出现“确认配置（不会启动业务）”；用户仍需再次明确点击才会沿用既有配置命令。

条件不齐、预览读取失败或状态读取失败均不会提交配置，不清空运营驾驶舱，也不会自动重试。配置预览固定声明数据库写入、配置写入、token 请求、业务处理和外部效果均为 false；`canProcessBusinessTasks` 固定为 false。

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

未修改 `apps/web/src/styles/45-ecommerce-workshop.css`，未覆盖既有样式改动。

## 验证证据

1. 后端配置预览、安装、生命周期接口及只读路由相邻回归：`208 passed`。
2. 扩展正式路由边界：`2 passed`；新增预览是 GET，原有三项 POST 命令集合未扩张。
3. 前端 client/component 专项：`32 passed`。
4. 前端正式源码全量：`329 passed` 个测试文件，`3176 passed` 项测试。
5. TypeScript `--noEmit`、Python `compileall`、Vite production build、`git diff --check` 通过。
6. Vite 保留既有大 chunk 提示；本波没有新增依赖或样式资源，不把该提示误报为本波失败。

## 方案一致性与风险复核

- 预览为 GET，无 query/body，无幂等键、Receipt 或数据库连接。
- 凭据只调用 `exists`；没有 `read`、token 交换或凭据正文回显。
- 服务端响应与前端 parser 均严格拒绝多余内部字段。
- 前端加载、状态刷新和预览均不自动 POST；配置仍由第二次明确点击触发。
- 未知 POST 结果仍进入待核对且不自动重发。
- 当前业务库保持只读，Host/worker/Provider 保持 OFF。

## 未完成边界

当前正式实例仍运行上一冻结版本。本结果只证明源码、合同与测试闭合；在形成独立提交并按既有冻结流程切换实例前，不宣称页面已经上线，也不计入真实经营八阶段验收。
