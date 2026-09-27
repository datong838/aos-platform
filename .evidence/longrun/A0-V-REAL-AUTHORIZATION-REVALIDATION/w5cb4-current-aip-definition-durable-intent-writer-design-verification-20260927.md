# W5CB4 当前 AIP 定义 durable intent 写入器设计核验（2026-09-27）

## 设计波结果

- 先有同目录 `w5cb4-current-aip-definition-durable-intent-writer-plan-20260927.md`。本次只固定代码和停止边界，未实现脚本、未创建 intent、未写 DB，不能称发布完成。
- 当前签名 Receipt 与 signed state 目录存在；尚无 `definition-publication-intent` 文件（只读文件清单检查）。当前 DB 上波独立只读仍 agent/skill/capability/binding 均 0；safe preview 8080/8434 200，浏览器六角色投影禁入。
- 当前三个 Owner `publish*` 方法分别持有并提交自己的连接，故 53 行不是单事务。设计采用 `O_EXCL` 唯一 durable intent 先于任何 Owner 写、显式目标库 connect_factory、exact 签名核验和写后逐键回读；任何异常/中间行只读冻结，绝不换 intent 重发。既有 adapter `publish_current_verified` 只接受 proof 类型，但仍必须由执行脚本在同一目标边界重新取得 proof。
- 当前 API 控制测试的历史签名目录夹具 2 个 setup ERROR 仍是已知环境缺口；下一编码波应建当前专用隔离测试，不恢复旧卷。产品页面不新增变化，浏览器只读验收复用上波明确禁入读回。

## 下一波

- 按本 plan 实现默认只读、`--execute` 必须显式 intent 的受控脚本及故障注入测试。代码/测试/verification 落盘并提交之前，不在当前新库执行。随后单列真实一次写入波；未取得完整成功/独立回读不进入 BG-00 绑定。
