# W5CB4 BG00dx｜签名 BI 准入页面只读消费验证

## 范围与实现

按本波文件级方案，运行实例职责候选只读链接携带当时 installationId/revision/ETag。上线审批页对有效 UUID 调用 `readSignedBIPlanAdmission` GET，严格解析响应；只在响应安装 ID、revision、ETag 与来源精确相同时显示“当前读回”。服务端 blocker 转中文下一动作。invalid/403/404/网络/解析失败、跨安装或来源版本漂移都没有 BI 提交动作；即使候选无 blocker 也明确只是只读候选，仍无写按钮。本波没有调用 `bi-preparation` POST 或生成 Receipt。

| 验证 | 命令与结果 |
| --- | --- |
| RED | `apps/web` 下四文件 `vitest run ... --reporter=dot` → exit 1，5 个新增断言失败（SDK、parser、安装链接、页面禁入）。 |
| 专项 | 同四文件 → exit 0，56 passed；随后补跨安装响应测试并由累计覆盖。 |
| 前端累计 | `./node_modules/.bin/vitest run --reporter=dot`（工作区 Node PATH）→ exit 0，314 files / 2739 tests passed；日志 `/tmp/aos-bg00dx-full-final.log`。 |
| 构建 | `pnpm --filter @aos/web build`（工作区 Node PATH）→ exit 0，TypeScript/Vite 通过；既存大 chunk 提示，日志 `/tmp/aos-bg00dx-build-confirm.log`。 |
| 差异复审 | `git diff --check` exit 0；SDK 新增方法只有 `apiGet`，页面无 BI POST、无客户端权限/签名重算，也未改 E16 Runtime Host 禁入按钮。 |

## 边界与剩余风险

BG00dw 正式来源审计为当前 `a0v_118`、growth1.12=0、Host identity/assignment=0、八候选全0、`formalReady=false`；本波没有用 mock 页面结果替代真实业务验收。当前正式 OIDC、签名当前安装、六 active 实例仍未齐，真实 GET 正向和 Plan POST 均未调用。browser-pilot 工具不可用，本波无浏览器截图/真实交互验收；这是未完成项。当前库只读，Host/worker/Provider 关闭，无商城源读取、旧 Run 重放或 push。

下一波 BG00dy：审查页面到受控 Plan 提交的命令合同、同一幂等键和未知结果只读对账；在正式当前实例具备身份/模板/实例之前保持产品按钮禁用。并行推进正式签发/checker/三身份/Host assignment/Owner 与八配置来源，首链仍以当前真实 Receipt/自然触发证据判断。
