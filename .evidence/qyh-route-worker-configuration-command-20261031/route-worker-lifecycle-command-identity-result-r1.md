# 后台处理配置命令专用身份实施结果 r1

时间：2026-10-31（Asia/Shanghai）
对应方案：`route-worker-lifecycle-command-identity-plan-r1.md`

## 1. 已完成

1. 新增后台处理配置命令专用数据库连接模块；
2. 受保护身份文件、同库异账号、禁止危险 DSN 参数的校验已落地；
3. 登录角色安全属性、无角色继承、最小 schema/table 权限、强制 RLS、硬租户策略及无其他表写权限校验已落地；
4. 身份验证阶段强制只读，验证提交后才允许一次配置回执事务；
5. `RouteWorkerBusinessEntryFactory` 默认配置回执连接已从通用业务连接切换为专用连接；
6. 状态读取、配置预览及显式测试注入保持原行为。

## 2. 修改文件

- `services/aos-api/aos_api/aip_route_worker_lifecycle_command_connection.py`
- `services/aos-api/aos_api/aip_route_worker_customer_lifecycle_wiring.py`
- `services/aos-api/tests/aip/test_aip_route_worker_lifecycle_command_connection.py`
- `services/aos-api/tests/aip/test_aip_route_worker_customer_lifecycle_wiring.py`
- `.evidence/qyh-route-worker-configuration-command-20261031/route-worker-lifecycle-command-identity-plan-r1.md`
- `.evidence/qyh-route-worker-configuration-command-20261031/route-worker-lifecycle-command-identity-result-r1.md`

## 3. 验证结果

### 3.1 测试驱动过程

- RED：新增测试首次收集时因实现模块尚不存在而失败，证明测试覆盖新入口；
- 环境前置：项目默认一次性测试 PostgreSQL 端口 5433 当前未运行，因此未使用当前业务库替代；
- GREEN：对不访问数据库的专项与相邻测试跳过全局数据库夹具，所有数据库连接均由测试替身接管。

### 3.2 专项与相邻回归

- 专用身份与工厂接线：27 passed；
- Route worker 业务入口、配置预览、客户生命周期、安装与安装权威相邻回归：69 passed，1 skipped；
- Python `compileall`：通过；
- `git diff --check`：通过。

### 3.3 正式运行边界只读复核

- `GET /v1/health`：HTTP 200；
- Web 首页：HTTP 200；
- `POST /v1/ecommerce-workshop/background-processing/configure`：HTTP 405；
- 受保护 Route worker 配置文件：不存在；
- API 仍监听 PID 11411 / 18080；Web 仍监听 PID 4054 / 18434。

以上运行检查只证明本轮未改变正式运行边界，不计为真实业务验收。

## 4. 方案一致性检查

- 方案要求“代码侧拒绝式接线、不准备真实身份”：一致；
- 方案要求“只允许 `bundle_installation_command` SELECT/INSERT”：一致；
- 方案要求“硬限制 `org-org/dev-project`，不只信任 session 变量”：一致；
- 方案要求“不影响配置预览和状态查询”：69 项相邻回归通过；
- 方案要求“不开放 POST、不写业务数据、不启动执行器”：运行复核一致。

## 5. 当前风险与剩余门

1. 真实 PostgreSQL 策略表达式尚未在独立测试库做集成验证；当前只完成代码与纯单元验证；
2. 当前业务库没有创建专用角色、授权、RLS 策略或受保护身份文件，这是预期的安全门；
3. 正式 API 仍拒绝所有配置 POST，用户当前不能执行“确认配置”；
4. 后续开通必须先在独立数据库验证完整 DDL 和策略表达式，再单独评审当前库准备动作，并等待用户明确确认配置。

结论：代码侧最小权限通道已闭合，当前运行与数据保持不变；不把本结果计为真实后台处理配置完成。
