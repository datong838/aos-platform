# 阶段评审 runtime proof reader 验证

日期：2026-09-12

基线：`4ef94c05`

结论：Task/Plan/Run、最新 StepRun、Checkpoint 与 Observation Evidence 已由同一真实只读路径生成可封印 runtime snapshot 和 `validate_runtime` exact 消息；职责、Eval/source proof reader 仍待后续。

## 验证

- portrait、diagnosis、solution-design 三阶段通过隔离 PostgreSQL 创建真实 Task/approved Plan/Run，执行 TAOR 四相并完成 Step/Checkpoint/Evidence。
- proof payload 使用数据库 actual observation，expected 为同一 subject exact ref；snapshot 固定 task/run status、plan ref、step attempt、checkpoint state/dependency hash 与 Evidence id/content hash。
- snapshot、payload、expected 全部通过项目 canonical JSON 校验。
- 兼容 `require_stage_review_runtime` 返回原 plan；plan/subject/attempt 漂移、后继已启动、checkpoint 缺失、跨租户和缺前序阶段继续拒绝。
- 定向 runtime/package 组合 `32 passed`；补充 canonical 断言后 runtime `6 passed`；compileall 与 diff check 通过。既有 7 warning 和退出 logging 提示未由本切片引入。
- AR2-7 closure 扫描 1777、分类 140、迁移 93；hash、正反依赖、跨层 import 与动态引用错误数组全部为空。

## SHA256

- reader：`3343ef47c153251837124874a76ae53bcb49a82130cbbd5c282b6a04507c8b9a`
- tests：`bcbf4dbe5d22e25a3d84ef20f3b618eeb5bc63882dd90f8783ae4d64259a043c`
- plan：`8f4e599ed30010caf6762f0c785e67cc570381e09517168367804e8812f91708`

## 下一门

按相同模式让责任计划/成员/Resolution Receipt reader 输出 `validate_review_slot` proof；再处理生成来源、Eval contract/report/gate 与原 query/Suite case hash。三者组合后才接 Owner binding，不把单个 proof reader 宣称为完整授权。
