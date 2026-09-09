# AR2-7D 资产控制三视口浏览器验收

日期：2026-09-10
分支：`m1`
基线：`816274f0`
结论：`AR2_7D_ASSET_CONTROL_BROWSER_GREEN`

## 1. 验收边界

- 生产页面固定为 `http://127.0.0.1:8434/apollo/assets`；使用 Chrome/Playwright 实点，不渲染独立测试组件。
- 浏览器路由夹具只投影 D6D2 已在隔离 PostgreSQL/OCI 证明的状态形状：第一代卸载、资源停止、旧审计保留；第二代重装、当前 generation、ready/enabled 和允许停用。
- 浏览器证据不替代 D6D2 authority；没有发出安装、卸载、runtime command 或其他 POST，没有真实租户 mutation、Provider、迁移、发布或 push。

## 2. 三视口结果

| 视口 | 结果 | 资产 GET / POST | 横向宽度 | 错误 |
|---|---|---|---|---|
| 1280×720 | PASS | 11 / 0 | 1280 / 1280 | page 0 / console 0 / HTTP 500 0 |
| 1440×900 | PASS | 11 / 0 | 1440 / 1440 | page 0 / console 0 / HTTP 500 0 |
| 1920×1080 | PASS | 11 / 0 | 1920 / 1920 | page 0 / console 0 / HTTP 500 0 |

每个视口均完成：

1. 打开安装管理并读取两条安装列表；
2. 选择第一代，验证 `uninstalled / stopped`、旧 generation 可审计、安装与 runtime 均无可执行动作；
3. 选择第二代，验证 `active / ready / enabled`、仅当前 generation 出现在 slot、服务端只允许“停用运行实例”；
4. 点击“刷新安装状态”，验证列表、当前详情、当前 runtime 三个 GET 均增加，POST 仍为 0；
5. 返回资产 Registry 后重新进入安装管理；
6. 实点侧栏折叠与恢复，滚动到 runtime/slot；
7. 加载本地签名资源形状，验证 slot 资源 GET 和 iframe 内“当前安装槽位已加载”。

全部资产请求的 `X-Org-Id/X-Project-Id` 均为 `org-org/dev-project`。旧 generation `33333333-3333-4333-8333-333333333333` 在第一代审计可读，但不出现在第二代当前 slot；当前 generation 为 `44444444-4444-4444-8444-444444444444`，安全周期为 8。

## 3. 制品

- `ar2-7d-asset-control-browser.mjs`：确定性只读验收脚本。
- `ar2-7d-asset-control-browser.json`：逐视口请求、断言、错误数组和布局结果。
- `ar2-7d-asset-control-{1280x720,1440x900,1920x1080}.png`：最终 PASS 截图。
- `ar2-7d-asset-control-diagnostic-{1280x720,1440x900,1920x1080}.png`：首次脚本选择器失败时的诊断截图，仅用于失败路径审计。

## 4. 失败路径与纠正

- 首轮使用精确文本定位安装名称，但同一表格单元格还包含 UUID，三视口各等待 30 秒后失败。诊断截图证明列表已正确渲染；改为按包含业务名称的行定位，没有放宽业务断言。
- 第二轮业务断言全部走完，但顶层 `addInitScript` 同时注入 sandbox iframe；iframe 按安全设计没有 `allow-same-origin`，读取 sessionStorage 产生 pageerror。修正为仅顶层窗口写入租户 session，不改变 iframe sandbox，也不忽略 pageerror。
- 目视复核发现仅等待 iframe 元素不足以证明 slot 内容加载；最终脚本增加 slot 资源 GET 计数及 iframe 正文可见断言。最终波次三个视口全部通过。

## 5. 哈希

| 文件 | SHA-256 |
|---|---|
| `ar2-7d-asset-control-browser.mjs` | `b90f07c9400071a195cfeaf22ace8d854ff266f5c0cf70c67cff887cba4e4d61` |
| `ar2-7d-asset-control-browser.json` | `0872fd66b143a26b47eb4a6a4ea0bc869b09e1bfbaa8ccc843aea2833e66ea4c` |
| `ar2-7d-asset-control-1280x720.png` | `c2c6071cb805bb888e2d58bac95df1bfeeb8a17ac2678a429827469f91eab906` |
| `ar2-7d-asset-control-1440x900.png` | `a24801d447b325bfe80c06903920d4fc39bf86bbc7b82c010c9c9011874d3d52` |
| `ar2-7d-asset-control-1920x1080.png` | `e052712015263502ea66d533006b16e188b16bfeec3bf83584e0aeb9ee70cdf5` |

## 6. 下一步

浏览器资产控制门已闭合；AR2-7D 尚未完成。下一步回到 `verify_closure.py --phase ar2-7` 的十项 Router/Web 最终切换红单，先补受控单写切换方案与实现，再做整波只读复核、closure/memory、无残留检查和最终 authority CAS。
