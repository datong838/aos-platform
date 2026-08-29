# R41 AOS 剩余侧栏当前可操作性与数据追溯验收

- 截止日期：2026-08-30
- 租户边界：`org-org/dev-project`
- 结论范围：AOS 剩余侧栏控制面与只读数据链当前截面；不授权 Provider、真实外部副作用、迁移或发布。

## 浏览器验收结论

1. R41-A～R41-G 均从产品侧栏进入；折叠组、返回链、页签、筛选、详情、刷新、可信空态与取消路径逐项点击。
2. 数据、文档智能、媒体集与运维页面不再用演示目录、固定生产节点、固定发布记录或开发方案编号补齐当前租户事实。
3. `/apollo` 根页只读当前租户舰队；发布通道变更、资产组合与安装仍由各自受控页面承接，本轮未创建节点、提升通道、制作或安装资产。
4. Release、Spoke、Ferry、变更审批、配置与密钥、SaaS 开通均验证失败关闭或取消路径；未发布、未回滚、未审批、未展示秘密正文、未创建租户。
5. 接入案例与资产 Registry 的业务主文案为中文经营语义；精确标识仍保留在审计/选择合同中，没有改变服务端选中坐标。
6. 浏览器检查期间只出现第三方浏览器遥测警告，没有观察到 AOS 业务 console 错误。

## 代码与回归证据

- Web 全量：266/266 测试文件、2341/2341 测试通过。
- Web 生产构建：TypeScript 与 Vite 构建通过。
- API 专项：`test_r41_current_data_truth.py`、`test_dataset_canonical_mapping.py`、`test_ontology_overlay_router_registration.py` 共 10/10 通过。
- 共享记忆：`memory-status` 为 `GREEN_WITH_WARNINGS`，全部强一致投影 `CURRENT`；`memory-validate` 为 `GREEN`。唯一 warning 是 Codex eventual note 尚待异步投影，不参与本轮授权判断。
- 工作树格式：`git diff --check` 通过。

## 仍然生效的安全边界

- 未触发 Provider、手工管道重放、真实外部业务派发、迁移、发布、回滚或 Secret payload 读取。
- R41 只关闭剩余侧栏控制面当前可操作性缺口；Workshop 八个业务菜单必须在 R42 使用当前栖月汇事实逐页重新验证数据、功能与视觉，不能继承旧结论。
