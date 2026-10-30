# 配置保存就绪语义正式只读切换方案 r4

时间：2026-10-31（Asia/Shanghai）

## 目标

把已通过冻结影子验证的提交 `1389d5ae6` 切换到正式 API，使运营页面真实显示第五项“配置保存通道尚未开通”。此次切换只纠正只读展示语义，不开放配置 POST，不写当前业务库或配置文件。

## 切换前事实

- 正式 API：PID 11411，端口 18080，health 200；
- Web：PID 4054，端口 18434，HTTP 200；
- configure POST：405；
- 正式受保护配置文件：不存在；
- 当前库专用命令身份文件：不存在；
- Host、worker、Provider、迁移：OFF；
- 冻结影子已证明：前四项通过、第五项失败、`approvalAllowed=false`，全部副作用为 false；
- 影子端口 18081 已关闭。

## 冻结源

- git archive：`1389d5ae6`
- 目录：`.evidence/qyh-route-worker-configuration-preview-runtime-20261031/private/api-source-1389d5ae6-r3`
- 既有受保护 dirty 依赖叠加：`aip_route_release_request_context.py`
- 依赖 SHA-256：`ba41413323e77b2fbd5a0566ad2a46718cbec64ec97a1038c980d293bda54b1f`

## 切换步骤

1. 再次核对旧 PID、端口、POST 405、配置文件不存在；
2. 停止旧 API PID 11411，不动 Web、PostgreSQL、Keycloak；
3. 使用与影子完全相同的显式 OFF 环境启动新正式 API，仅端口改为 18080；
4. 不设置 `AOS_ROUTE_WORKER_CONFIGURATION_POST_ENABLED`；
5. 不设置 `AOS_ROUTE_WORKER_LIFECYCLE_COMMAND_CREDENTIAL_FILE`；
6. 验证 health 200、未登录预览 401、configure POST 405；
7. 使用短期本地机器身份只读获取配置预览，确认五项状态与影子一致；
8. 验证 Web 原 PID、配置文件缺失、18081 无监听。

## 回滚与停止规则

- 新进程未监听或 health 非 200：停止该新 PID，使用原 r4 启动器恢复旧冻结源；
- 任一 POST 非 405、配置文件出现、当前库发生已知写入：立即停止新进程，只读对账，不重发；
- 启动结果 unknown：先查 PID、端口和 health，禁止盲目再次启动；
- 不修改长期 Goal，不启用任何执行器。

## 成功标准

- 正式 API 单实例监听 18080；
- 正式只读预览显示前四项通过、配置保存通道未通过；
- `approvalAllowed=false`、`canProcessBusinessTasks=false`；
- configure POST 仍为 405；
- 当前业务库、配置文件、Web 与所有执行开关保持不变。

以上只证明展示语义与门禁一致，不计为真实客户配置或经营首链验收。
