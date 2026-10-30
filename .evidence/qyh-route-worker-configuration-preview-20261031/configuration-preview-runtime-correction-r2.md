# G7-M｜后台处理配置预览运行接线纠正 r2

时间：2026-10-31 02:10（北京时间）

## 业务结果

当前客户安装已通过正式只读校验；后台业务身份、受保护保存位置和身份凭据仍待补齐。因此页面应显示“后台处理配置条件未齐”，不出现最终配置确认，也不能处理业务。

这次纠正推翻了 r1 中“需要给独立目录身份形成安装读取能力”的诊断。真实原因是代码把安装、锁和签名证据误接到了 Host 目录身份；目录身份按既有三平面隔离设计本来就不应读取这些控制面表。修复没有扩权，而是让安装证据 reader 使用 API 控制面登录建立原始连接，再由 reader 自身在首条业务 SQL 前进入 `REPEATABLE READ READ ONLY` 并应用精确租户范围。

## 修改与一致性

- 方案补充：`configuration-preview-plan-r1.md` 新增 r2 连接平面规则。
- 产品实现：`services/aos-api/aos_api/aip_route_worker_installation_authority.py`。
- 回归测试：`services/aos-api/tests/aip/test_aip_route_worker_installation_authority.py`。
- 产品提交：`af609f2ee8fb230545583046ea464509d7dc2ee0`。
- 代码和冻结运行副本 SHA-256 均为 `468847a17a6faaa17796ea2a004d92a65b3795d04577ce1183c70ac556ccddd2`。

实现与方案一致：Host assignment 仍只使用目录身份；没有修改 `runtime_directory_connection`、角色、ACL、数据库、受保护凭据文件、安装数据或签名校验。

## 自测与运行核验

- 专项 18 项通过。
- 安装、身份、配置预览、HTTP 范围和三平面连接相邻回归 244 项通过。
- Python 编译与 `git diff --check` 通过。
- 首轮测试因本机默认测试端口 5433 未运行而在测试夹具初始化阶段失败，未进入任何测试正文；随后按无数据库单元测试方式执行并全部通过，未连接或修改当前业务库。
- 当前权威安装只读核验：current 与 active 均为第 5 版，4 个签名组件通过。
- 新冻结影子 API 启动后，OpenAPI 只暴露 GET，未登录访问返回 401；随后正式 API 单实例切换到 PID 7614，Web PID 4054 保持不动，影子端口 18081 已关闭。
- 正式 API 日志确认迁移关闭、Runtime Host 关闭、定时 worker 关闭、逻辑自动化 worker 关闭、Provider 健康维护不活动。

## 风险与验收边界

所有预览副作用仍为 false：不写数据库、不保存配置、不申请 token、不处理业务、无外部效果。当前只闭合了“当前客户安装”这一项配置前置；另外三项仍待补，八阶段数字不变，也不构成自然经营首链或完整 Goal 验收。
