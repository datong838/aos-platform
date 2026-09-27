# W5CB4 当前源码四包 Registry 发布核验（2026-09-27）

- 按 `w5cb4-current-code-registry-publish-plan-20260927.md`，在专属新库 `aos_current_preview_20260927@a0v_106`，先只读对齐签名 Receipt、树哈希、四包 ReleasePolicy/内容摘要、零既有 Registry 版本和零安装；默认 preflight 返回 `CURRENT_REGISTRY_PREFLIGHT_GREEN`。
- 显式发布前留外置 `registry-intent.json`；经正式 RegistryService 的 creator、validator、publisher 分工，一次执行得到 `CURRENT_REGISTRY_FOUR_PUBLISHED`。Store 每包 exact 读回；独立 SQL 联查四包状态均为 `published`：core 1.4、Niushop 1.23、growth 1.11、operations-base 1.2。`bundle_installation=0`，`dev-org` 的 TWA org=0；Provider 与外部发布=0。结果保留在 `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/registry-state/registry-result.json`，SHA256 `b7b10afe6d2a83287b58554752ead988e4652ce4eb79f8905d41330433846c88`。
- 当前新 Registry 已发生 4 包正式发布，这是本地隔离库控制面变更，不是外部业务发布。原 `aos_meta_head` 未迁移，8080 仍指原隔离克隆，商城源/旧 12 Run/自然 worker/Provider 未触。
- 专项与历史首装邻接 `13 passed, 7 warnings`；脚本编译和 diff 检查通过。已有 publish state 会直接拒绝重跑，未知部分状态应由 Registry Store 与 intent 只读对账。
- 下一波：以四包当前 RegistrySnapshot 走无 baseline Composition、Installation maker 创建/提交与不同 checker exact 批准；缺 Runtime 配置则停 approved，不强行启用或切页面。当前四发布版本不等于八工作台可用，浏览器目录尚未通过。
