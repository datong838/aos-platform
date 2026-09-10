# AR2-7E 浏览器网络拒绝日志分类补充方案

日期：2026-09-10
基线：`6392cf6b`
状态：执行器修正前冻结

## 1. 确定性发现

第一轮有效 Catalog 修正后，cockpit 两个视口的 module Shell、专用页头、八模块导航、唯一 active、租户头和只读请求均正确；唯一失败项为 Chrome 对每个预期 HTTP 403 输出：

```text
Failed to load resource: the server responded with a status of 403 (Forbidden)
```

两单元共 40 条，`pageerror=0`、Workshop 非 GET 请求为 0。这是隔离 fixture 明确拒绝真实业务读取的浏览器网络提示，不是 React 未捕获错误或产品逻辑异常。

## 2. 最小修正

只修改 `ar2-7e-eight-workbench-browser.mjs` 的诊断分类：

- 所有 `console` error 仍逐条采集；
- 仅把文本精确匹配 Chrome 403/503 `Failed to load resource` 的条目放入 `expectedNetworkConsoleErrors`；
- 其他 error 继续进入 `consoleErrors` 并判 FAIL；
- JSON 顶层分别汇总预期网络拒绝提示与未预期控制台错误，不能删除或覆盖原始消息；
- HTTP 响应列表仍保留精确状态和路径，非预期 5xx、page error、非 GET、租户漂移仍判 FAIL。

不修改产品源码、响应状态、Catalog 权限或页面错误处理，不把真实数据接入 7E。

## 3. 退出

修正后从头运行矩阵。`consoleErrors=0` 只表示未预期应用错误为 0；`expectedNetworkConsoleErrors` 必须大于 0 且能与隔离 403/503 响应解释一致。若仍有其他错误或同阶段再连续失败两次，继续停止并分析，不强行转绿。
