# 阶段评审五门 composite authority reader 方案

日期：2026-09-12

基线：`1cf8ab65`

## 合同

新增同步 `StageReviewCompositeAuthorityReader`，只组合现有 command identity、responsibility、runtime、Eval/source proof。五个 exchange 固定顺序 command、slot、runtime、Eval、structure；snapshot 组合命令 hash 与三个真实 proof snapshot，不复制 query。构造时复制并校验非空 markings，命令 body 无权覆盖。

Owner binding 向 reader 传入 key/expectedVersion；其他调用和双事务逻辑不变。任何 proof shape/kind/JSON 漂移均在 IPC 前拒绝。

## 文件与验收

- 新增 composite reader 与单元组合测试。
- 修改 Owner binding 及其真实 PG 测试签名。
- 新增本 plan/files/verification，更新 closure。
- 验证五门顺序、payload/expected exact、snapshot canonical、markings 复制、组件异常传播及 Owner 发布回归。

下一波把 composite reader、Owner binding、database phases、installed port 装配成内部异步 service，并实现 Receipt replay fast path；仍不新增公开入口。
