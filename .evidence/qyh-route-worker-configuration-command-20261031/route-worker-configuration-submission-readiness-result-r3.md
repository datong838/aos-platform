# 后台处理配置保存就绪语义实施结果 r3

时间：2026-10-31（Asia/Shanghai）
对应方案：`route-worker-configuration-submission-readiness-plan-r3.md`
产品提交：`1389d5ae6`

## 1. 业务结果

配置预览已从“四项材料通过就显示可以确认”纠正为“五项全部通过才允许确认”。新增第五项为“配置保存通道”，它同时要求：

1. 配置回执专用数据库身份通过只读最小权限校验；
2. 正式运行显式开启精确配置 POST 门禁。

当前正式环境未满足这两项，因此真实业务表达现在应为：四项配置材料已准备，但配置保存通道尚未开通，运营人员当前不能确认保存。

## 2. 代码改动

- `services/aos-api/aos_api/aip_route_worker_lifecycle_command_connection.py`
  - 新增始终只读的 readiness probe；验证后回滚并关闭连接，绝不切换为读写。
- `services/aos-api/aos_api/aip_route_worker_customer_lifecycle.py`
  - 配置预览合同固定为五项，并把保存通道纳入一致性校验。
- `services/aos-api/aos_api/aip_route_worker_customer_lifecycle_wiring.py`
  - 保存通道必须同时满足显式环境门和只读数据库 probe。
- `scripts/a0v_qyh_restored_http.py`
  - 默认继续拒绝所有变更；仅当严格布尔门为真时，才把精确 configure POST 交给产品认证与业务门禁。
  - disable、restore 和所有其他 POST 继续拒绝。
- 对应专项、HTTP 外壳及业务 API 测试已更新。

## 3. 自动验证

- Route worker、配置预览、客户生命周期、安装权威、专用身份、HTTP 外壳与生命周期 API：`172 passed, 1 skipped`；
- Python compileall：通过；
- git diff check：通过；
- 只读 probe 测试证明：校验全过程保持 read-only、零 commit、显式 rollback、连接关闭。

跳过项为既有环境相关测试；本轮未使用当前业务库替代测试前置。

## 4. 冻结影子运行

影子源以提交 `1389d5ae6` 的 git archive 为基线，并精确叠加受保护的既有 dirty 依赖：

- `services/aos-api/aos_api/aip_route_release_request_context.py`
- SHA-256：`ba41413323e77b2fbd5a0566ad2a46718cbec64ec97a1038c980d293bda54b1f`

叠加没有修改原 dirty 文件。探针增加自包含检查，若加载冻结目录外的任何 `aos_api` 模块即失败。

影子运行结果：

- health：HTTP 200；
- 未登录预览：HTTP 401；
- 默认 configure POST：HTTP 405；
- 使用现有短期机器身份进行只读 GET 后：HTTP 200；
- 当前客户安装、后台业务身份、受保护保存位置、身份凭据：均通过；
- 配置保存通道：未通过；
- `status=needs_input`、`approvalAllowed=false`；
- 数据库写入、配置写入、token 请求、业务处理、外部效果：均为 false；
- `canProcessBusinessTasks=false`。

测试客户端为取得 GET 访问令牌执行了一次本地 OIDC 认证；该令牌未打印、未持久化。预览请求自身没有申请 token，响应中的 `tokenRequest=false` 含义未被改变。

影子验证后已停止 PID 37215，端口 18081 已关闭。

## 5. 正式运行边界

- 正式 API 仍为 PID 11411，health 200；
- Web 仍为 PID 4054，HTTP 200；
- 正式 configure POST 仍为 405；
- 受保护配置文件仍不存在；
- 当前业务库未创建专用角色或策略；
- Host、worker、Provider 和迁移仍关闭。

## 6. 方案一致性与风险

- 默认关闭：一致；
- 缺少数据库通道时失败关闭：一致；
- 未显式开 POST 时不探测数据库并保持失败关闭：一致；
- 仅精确 configure 可被未来门禁放行：一致；
- 不把四项材料通过误报为可保存：一致；
- 当前正式进程未切换，因此用户当前页面仍运行旧预览代码；这不是业务验收。

下一步若要让正式页面立即反映第五项，需要把提交 `1389d5ae6` 形成新的完整冻结叠加源并受控重启正式 API，但仍保持 POST 门禁关闭。该重启只纠正展示语义，不授权当前库写入或用户配置。
