# W5CB4 当前签名包 AIP 定义发布接续波（2026-09-27，编码前）

## 上位与问题

- 承接 `w5cb4-current-six-role-projection-diagnosis-verification-20260927.md`：新库 6/37/10 正式定义为 0，签名 growth 包 `1.11.0` 已 published、installation approved，但 Runtime binding 0。231 BG-00/03/04 要求六角色使用公共 AIP Owner，不允许从旧 `1.3.0` 源树伪装当前安装。
- 当前签名包目录已有 agents/logic/capability JSON，但是否完整、签名覆盖、与旧 `AipSolutionPackPublisher` 合同一致须先核验。现有 publisher 仅接受 `1.3.0`，source revision 写死 `1.2.0`。本波不得先改常量就发布。

## 串行步骤与文件级

1. 只读核签名包 exact Registry/签名/内容回读，统计当前 6/37/10、compatibility map、schema/policy、分析模板及发布器依赖文件；对比旧源码并列出差异，不读取商城源。
2. 若内容合同可映射，先在 `aip_solution_pack_publisher.py` 或新的窄 adapter 中设计当前包版本/source revision 参数，保留旧版兼容与 tenant isolation，拒绝未签名或来源漂移；细化测试文件清单后才编码。若签名包缺必需对象，停在构建/包合同修复，不向 DB 填行。
3. 隔离库专项测试先证 6/37/10、重复幂等、错版本/坏签名失败、跨租户；再为当前新库制定唯一发布 intent/结果边界。未知提交只读对账，不重发；发布后独立只读回读 definition source exact，浏览器投影仍不得因无绑定显示 ready。
4. 累计回归、浏览器验收、方案/代码一致性复审、verification→m1 提交后进入下一波。

## 第 1 步发现后的波界收紧

- 当前签名包 6/37/10 完整，但既有 publisher 的写入 source revision 与 installer 读取过滤器同为旧 `1.2.0`；单改版本常量或执行脚本会在新库产生错误来源，也可能使旧库的六角色目录消失。当前 publisher 还只接收任意本地目录，不负责签名/Registry exact 验证。因此本波到**可行性与兼容性审计**收笔，余下 2–4 步移入下一波单独文件级设计；未编码、未发布、未触碰当前库。不是把 plan 当成完成发布。

## 停止条件

- 不运行旧版 publisher 直接发布，不 SQL 手填，不触发 Runtime/Provider/自然 worker、商城源或原 12 Run；现有预算/出站/数据分类草稿尚未 active，投影仍应禁入。
