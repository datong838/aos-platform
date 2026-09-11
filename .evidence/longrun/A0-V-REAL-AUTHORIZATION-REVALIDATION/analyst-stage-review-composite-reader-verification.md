# 阶段评审五门 composite authority reader 验证

日期：2026-09-12

基线：`1cf8ab65`

结论：command、responsibility、runtime、Eval、structure 五门已组合成固定 exchanges 与单一 authority snapshot，并可直接供 StageDecision Owner 双事务使用；内部异步 service/replay fast path 尚待下一波。

## 验证

- 顺序固定为 command identity、review slot、runtime、Eval proof、structure case。
- markings 在 reader 构造时复制；测试修改原列表后 Eval reader 仍只收到原值。
- composite snapshot 只含 command payload hash 与 responsibility/runtime/eval-source snapshots，不复制 query；五个 payload/expected 由 prepared 另行封印。
- responsibility/runtime 组件 shape 在读取 plan 前检查，避免 KeyError；Eval 组件也要求 exact 五字段。
- Owner binding 现在传递真实 key/expectedVersion，真实隔离 PG 五门发布、竞争漂移、replay 拒绝保持。
- 定向组合 `75 passed`；完整阶段评审 `182 passed`；compileall/diff check 通过。既有 7 warning 与退出 logging 提示未由本波引入。
- AR2-7 closure 扫描 1778、分类 141、迁移 93；所有错误数组为空。

## SHA256

- composite：`9aaa2a81022e0012927dead1fcfeeb5cd538b8d4119b2352a3672cc40ae3c903`
- Owner binding：`d64be783285bc142c31b74bc6ba4651cc9b13eb9b401b1724ec3172ce46ffa98`
- composite tests：`b387739cdd98e98b6f45ab4c2c85f4680312db6e4294829523441fc5da3c5af7`
- Owner tests：`69fa86a1cda5fa6ade8505ccb6d8a4c4ee0c3fe6e1baaa34ebd8d62c914bc74a`
- plan：`aa442bee6dd18335ae1e47fa79e42c5f902fabb379c7413c1d5ad30f874d4339`

## 下一门

装配内部异步 service：scoped transaction factory + composite reader + Owner binding + database phases + installed port + coordinator；在进入五门前增加精确 Receipt replay fast path，历史重放不重读失效来源、不调用包。
