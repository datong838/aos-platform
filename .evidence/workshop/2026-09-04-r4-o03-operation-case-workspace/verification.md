# R4-O03 运营案例工作区闭环证据

## 结论

R4-O03 已把订单、库存、履约、支付、售后事件和既有运营案例组合为同租户、同截止面的只读工作区。工作区只用 exact 资源引用核对归组关系，数量账本满足 `来源总量 = 已归组 + 未归组`；来源失败时保留其余正式事实并明确标记部分可用，不把未知值写成零，也不触发外部业务动作。

## 文件范围

- `services/aos-api/aos_api/ecommerce_operation_case_workspace_contracts.py`
- `services/aos-api/aos_api/ecommerce_operation_case_workspace.py`
- `services/aos-api/aos_api/routers/ecommerce_workshop.py`
- `services/aos-api/tests/test_ecommerce_operation_case_workspace_contracts.py`
- `services/aos-api/tests/test_ecommerce_operation_case_workspace.py`
- `services/aos-api/tests/test_ecommerce_operation_case_workspace_api.py`
- `.evidence/workshop/2026-09-04-r4-o03-operation-case-workspace/`

没有迁移、外部 Provider、退款、发货、发布或真实业务写入；没有读取或覆盖其他开发范围的未提交内容。

## 专项与累计回归

- 工作区契约、服务、API 专项：10 项通过。
- 运营案例合同、存储、跨域对象读取、运营视图合同与 API 累计回归：52 项通过。
- Python 编译检查通过。
- `git diff --check` 通过。

关键覆盖：

- 规范来源顺序与六类来源完整性；
- exact hash 一致才计为已归组，同一资源编号但 hash 漂移仍为未归组；
- 库存缺字段、售后待跟进候选只从未归组正式事实生成；
- 单来源失败保持其余来源可读并返回 `partial`；
- 案例或成员跨租户漂移时只关闭案例来源，不隐藏当前租户其他事实；
- 无时区截止面在读取任何来源前失败关闭；
- 接口拒绝 query scope 注入与非 GET 方法；
- 模块未安装时 404，OpenAPI 只暴露 GET。

## 栖月汇真实数据探针

后端使用标准本地恢复脚本重启，进程归属检查为 `RUNTIME_OWNER_EXACT`，健康接口返回正常。

真实租户 `org-org/dev-project`：

- HTTP 200，响应摘要 `224a78a659296cd09860e1fbf350227687542d4192708e1565968e9efeb6f8e3`；
- 六类业务来源均可读：订单 50、库存 50、履约 19、售后事件 0、支付 50、运营案例 0；
- 守恒账本：来源 169、已归组 0、未归组 169、候选 9；
- 9 个候选均为库存正式来源缺字段的核对事项；
- `externalEffectAllowed=false`。

负租户 `dev-org/dev-project` 返回模块未安装 404，没有返回栖月汇数据。结构化摘要见 `real-tenant-summary.json`。

## 内置浏览器验收

在 Codex 内置浏览器刷新 `http://127.0.0.1:5173/workshop/operations`：

- 左侧完整主导航保持可访问，电商八工作台与 AIP、模型、本体、数据菜单均存在；
- 统一运营页仍显示七类正式业务视图；
- 当前可见总账保持 `来源 219 / 已挂接 210 / 数据差异 9`；
- 订单、库存、履约、支付、售后事件、运营工单切片与内部安全预检仍可见；
- 页面未因新增后端工作区接口发生功能或导航回归。

浏览器直接访问 8080 端口被内置浏览器客户端策略拒绝，因此接口内容由同一运行实例的真实 HTTP 探针验证；浏览器验收聚焦实际工作台页面及其可见功能。本波没有通过其他浏览器控制通道绕过该策略。

## 方案与代码一致性复审

- 与 R4-O03 冻结方案一致：复用既有 `OperationCase` 权威存储和命令链，不新增第二套案例表或迁移。
- 本波只负责组合、候选识别和只读查询；创建案例仍由既有治理命令承接，并留给自动进入的 R4-O04 页面工作流调用。
- 真实案例数为 0 如实展示，不制造演示案例；9 个候选是当前正式库存事实的可追溯结果，不是开发任务编号。
- 风险边界保持：本波不授权真实外部副作用，不把页面或测试通过解释为运营执行完成。

结论：R4-O03 可以闭合，并自动进入 R4-O04 运营案例页面工作流。
