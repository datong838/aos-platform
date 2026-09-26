# W5ca6｜过期行动清单只读核对

计划 `m1@c04b87cb`，现场扩大修订 `m1@a5ff4ef0`。231 主线要求 A0-V 真实准入先于 A1，230 L0 未获授权。W5ca5 原组结论为十二 Run 仍 running、真实 closure no-authority。

- CAS 前 `authority.json` 为 `AOS-000720`，`next_steps=67`、`completed=191`、`incomplete=99`、`hard_boundaries=13`。
- 从 67 条行动抽出的 55 个唯一旧波号为 W5c6d–W5c8f；逐个核验均有 `completed` 项、verification 文件及 m1 历史提交。特别 W5c8a–f 的已提交 verification 为 `5dd544cd/c65bc58a/04591d78/0e86ad3c/649a039c/7d923a5c`。不能把旧“先方案”再次当作待办。
- 其他行动含重复“等待原十二 Run 严格 24h”及早期“real DB/Host 不变”等路线性提醒。W5ca4 已核 24h 为 `ELIGIBLE_NO_AUTHORITY`，故等待语句已失效；真实关闭仍被 Fleet/Host/Owner/历史行权威阻断，写入 `incomplete` 和下一门。
- 本波仅更新导航性的 `next_steps`，不清理 99 条 `incomplete` 或 13 条 `hard_boundaries`，也不把历史 GREEN 当 live。18181 `/docs` HTTP 200；8080 无 listener，不能做业务浏览器验收。

唯一当前行动：取得可信部署/资产控制面全量 Fleet（所有启动面、旧入口撤权、逐节点 ACK）与合法的独立原始行证明；若后者不存在，需正式“不接受业务结果”的退休决策。取得前不得对原组调用 closure、ACK、source read、worker/run replay。
