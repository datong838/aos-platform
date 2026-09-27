# W5CB4 当前安装配置阻断摘要与正式入口核验（2026-09-27）

## 结果与边界

- 按 `w5cb4-current-preview-config-blocker-ui-plan-20260927.md`，增加当前租户八类 head/revision 的只读候选计数。先经现有 `RuntimeViewReader.get_installation` 核验安装可见性，再以应用 read-only 连接设置租户作用域读取；不可见安装不查询计数，权限/SQL/形状异常只返回 `RUNTIME_CONFIGURATION_CANDIDATES_UNAVAILABLE`，不把 unknown 当 0。
- 新 GET 回显 installation ID/revision/etag，`authorityKind=tenant_candidates_not_installation_binding`。前端只有身份和版本与当前运行视图一致、读回未过期才逐项显示；即便八项都有候选，也不宣称安装已绑定或可运行。原 `allowedActions` 控制和运行命令未改。
- 当前新库应用只读连接实际读回八项均 0。浏览器 8434 `/apollo/assets` 安装管理选中唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`，显示 approved/revision 3、`not_prepared`、无运行绑定、八项“缺少当前候选”；职责计划和模型配额链接指向已有正式页面，其余明确“产品配置入口待建”。这是阻断解释，不是 BG-00 业务配置完成。
- 新 8080 预览启动 preflight `CURRENT_PREVIEW_HTTP_STARTING` 明示 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`；health 200，8434 仍可达，18181 无监听。未点 Apply/启用，未调用 Provider/商城源/旧 Run，未变更现有配置记录。

## 测试与复审

- 后端：`test_runtime_configuration_candidates.py` + `test_runtime_installations_api.py`，24 passed。覆盖八零、部分、全部候选但非运行授权、坏结果、不可见安装先阻断、读失败不泄漏详情。
- 前端：安装页/读钩子/解析器/SDK/冻结操作合同相关七文件，55 passed；TypeScript `tsc --noEmit` 通过。浏览器 AX 和截图读回八项及两个链接。
- 累计回归最初揭示冻结 M2-B `ASSET_CONTROL_OPERATIONS` 必须保持 23 项；已撤回对该注册表的扩展，只读摘要在 SDK 用规范化 ID 与静态路径调用，原测试 4/4 恢复。`pnpm` 自动改写过锁文件，已精确恢复，最终不提交锁文件。`git diff --check` 与提交前精确 staged 检查通过。
- 方案/代码一致：仅增加只读候选与产品阻断展示，不伪造八类配置、安装绑定、预算或审批；未改变 Runtime 状态机和原正常功能。后续真正的正式配置表单与 exact 绑定/运行准入仍缺，不能把本波计入 A1 自然首链完成。

## 下一波

- 返回 P2g30b 当前 RETURN Action 正向 producer：以既有失败的隔离 RED 为起点，在同一事务绑定 ReturnDecision、唯一 queued attempt、冻结 Brief、当前 dispatch/Capability/金额，并在 maker/checker 重核；若正式来源不闭合，只保留 RED，不造权限。
- 配置产品入口的余下六项作为并行待办切片串行交替推进，不死磕旧失败快照或十二 Run 的每行历史。
