# 阶段评审结构化 Eval 输入 hash 消息验证

日期：2026-09-12

基线：`d46ba850`

结论：Growth 作者包 review operation 已增加第五种无副作用结构 hash 校验；宿主五门编排和 Owner 完整门同步完成。当前 1.4.0 未改变，真实复合 authority reader 仍待下一波。

## 验证

- portrait、diagnosis、solution-design 三阶段使用现有真实 generation prompt，包内派生 structure case 并返回与 Eval input canonical hash exact 相等的唯一字段。
- expected hash 不符立即拒绝；既有 strict `_exact` 拒绝缺失/额外字段，包内 parser 继续拒绝非法 query/stage/来源与重复 JSON key。
- installed port 支持第五 kind 且仍一次调用；PermissionError、超时、取消和 response drift 不重试。
- prepared 上限从 4 精确扩为 5，并新增 6 条 exchange 拒绝；Owner 要求五 kind 唯一齐全。
- 首轮定向 31 项中 29 通过，2 项仅因旧断言仍匹配 “four exact” 失败；同步断言后联合 94/94，通过扩大阶段评审回归 178/178。
- 五个生产模块 `compileall` 通过；`git diff --check` 通过。既有 7 条 warning 与 pytest 退出后的 JDBC 空缓存 logging 提示未由本切片引入。
- AR2-7 closure 扫描 1777、分类 140、迁移 93；hash、正反依赖、跨层 import 与动态引用错误数组全部为空。

## SHA256

- package dispatcher：`aafb1c7938c8a920666194ea353918d1965399bce89fcff5170f2f4cb165cb4c`
- package review operation：`216105dc5035f3ea7e048d131a403390e977f2ba6afe540df98054fe9e4eeed7`
- host port：`76a8886b1ac8cfe7e12a0b955b77956fdc004efbaab61f4b1da532c2c4220b59`
- coordinator：`3b381dafdf22d61893d1fdce5ff3fb51873c1cfeaf44478615e217a6ae5710f4`
- Owner binding：`179b6dba153cdfd3ffd0b4da06cd4c226e8ebdf9fe8d19a20c1c7dcc7c3805e4`
- operation tests：`616304d28f3ff4a7353405a327e3caff967251d5032606e10b9f378d259554d9`
- port tests：`4a0a91a2264415e02fcb9bdaaa7b6b443d4235a64eb83f2d8cdb3c430657613e`
- coordinator tests：`96df3afba850c733fdd4f77af76e6a9b33a43dd5aebc668d2be7f7fe8ef02e09`
- Owner tests：`5e2a61bdac796779c1e6eb2a94d3475969dd7bccfd4864fa95572586863bb68b`
- plan：`57bf5bde073b15136059fff3f718d459a46c983e1a1816793253577b41ad1bf1`

## 边界与下一门

本切片未安装新版本、未调用真实租户、未完成复合 reader。下一波从事务一读取原 Agent query 与当前 Suite case input hash，连同 Task/Plan/Run、Checkpoint/Observation、职责、Eval proof 形成五条 exchange；事务外执行第五门后，事务二重读 exact snapshot，才能移除旧事务内 `derive_structure_case`。
