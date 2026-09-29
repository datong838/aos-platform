# W5CB4 BG-00ay｜approved 安装无 binding 诊断核验

方案：`w5cb4-bg00ay-approved-no-binding-diagnosis-plan-20260929.md`。本波仅复核现有代码、专项测试与当前签名安装只读预检；没有修改运行逻辑或当前数据库。

| 证据 | 命令/文件 | 结果 |
| --- | --- | --- |
| 当前安装 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` | 退出码 0；`aos_current_preview_20260927`、`a0v_114`、approved 1、published 4、runtimeBindings 0；签名根为同一签名构建目录。 |
| 状态语义 | `services/aos-api/aos_api/extension_runtime/runtime_view.py::_derive_control_state` | approved 且无 binding 投影 `not_prepared`，服务端原始允许动作 `runtime-apply`；不代表当前 Host/Owner 可执行。 |
| 客户端准入 | `apps/web/src/pages/s2/AssetBundlesPage.tsx:251-257,110-130` | 仅安装 ID/revision/ETag 与运行视图一致、`preparationExecutable === true` 才提交准备/验证。 |
| 产品诊断 | `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.tsx:100-151,153-165,185-211` | Host/Owner 未核验时禁按钮并显示告警；八类候选只对当前读回展示，缺失与未知分开；无绑定明确显示。 |
| 专项测试 | `pnpm --dir apps/web exec vitest run src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx` | 退出码 0，9 passed，含 Host 无 assignment 禁准备与八候选读回过期防误报。 |
| 当前进程 | `curl /openapi.json`、`curl :8434/aip/skill-publish`、`lsof :18181` | 8080/8434 各 200；18181 无监听。`/health` 返回 404，非本 API 的健康路径，不作为健康失败或通过。 |

结论：预定的确定性只读诊断已存在，无 RED 缺口，本波不写重复代码。正式 Host 凭据/assignment/Owner、八配置候选、绑定和首链仍未成立；页面禁入和专项测试只证明安全控制，不证明业务闭环。浏览器 pilot 未提供可调用工具，本波没有截图验收。

下一波 BG-00az：审当前产品八配置候选中首链所需最小合法来源与具体激活 Owner；优先找可独立完成的来源预检/错误诊断缺口，先方案再 RED/最小修复。缺正式 authority 的实例只阻断该实例，不启 Host、不写当前库。
