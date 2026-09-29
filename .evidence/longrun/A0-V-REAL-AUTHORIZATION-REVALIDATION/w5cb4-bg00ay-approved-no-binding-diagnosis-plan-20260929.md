# W5CB4 BG-00ay｜已批准安装无绑定的只读恢复诊断

## Rules 与上位方案

依 231 E03/BG-00、E16 运行准入失败封闭和 BG-00at 当前安装盘点：先读安装/运行视图、页面状态与现有测试；只修确实缺失的确定性诊断。当前权威库只读，正式 Host/Owner/配置不齐时禁运行准备；不读商城源、不重放旧 Run、不使用假账号或 mock 充业务证据。

## 文件级计划

1. 核对 `services/aos-api/aos_api/extension_runtime/runtime_view.py` 的 approved/binding 空态及 `apps/web/src/pages/s2/AssetBundlesPage.tsx`、`apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.tsx` 的安装修订、准入与候选显示。
2. 核对对应前端/后端测试。若已确定性说明空绑定、八类候选与 Host/Owner 未核验并禁用准备，则不写重复代码；否则先 RED 后最小修复上述具体文件。
3. 用当前签名 Receipt 的只读预检和专项测试复核，不把页面或单测当首链完成；记录下一波独立最小项。
