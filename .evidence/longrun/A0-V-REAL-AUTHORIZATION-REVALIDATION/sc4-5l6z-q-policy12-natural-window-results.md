# SC4-5L6Z-Q｜Q Policy12 真实自然空窗结果

日期：2026-09-17。代码基线：`28ed3ba9`。

## 权威恢复

- Q SourceSelection、RuntimeControl 已新建；schedule control binding 从 revision17 精确续到 revision18/hash `sha256:aea3184b0d99eb9b5833eff8dd60e47738d8153dc39791a03e07668a1161fe3f`。
- Policy12/hash `sha256:c86bdb6c2ff21ab5a4f006d523bdb35e8fe86beff6f2b115af2f7b919bd3e6c0` 与 Case14 已经 exact 审批并由 Q canonical router 保存。
- event-control 经独立审批扩展，十路均指向 Q epoch3/group55；Policy12 binding1 已审批启用。

## 自然窗口

- 计划在 05:54 开启，06:00 自然 Cron 产生唯一 run `scr-7b02d6ff15e44b38`；run succeeded、rows_written=65、executor_stopped=true。
- 同 run 形成唯一 ingress，source revision `a84b6c79-8654-48f0-98c2-57d41b067b3d`。没有手工 run、没有源库写入、没有第二次 source call。
- ProductEvent Worker 连续检查 Q，结果 `targetsChecked=1 / candidates=0 / occurrences=0 / failed=0`。因此这是“真实读取成功，但相对现有事件游标没有商品业务变化”的合法空窗；不是模型超时，也不是 worker 故障。
- 06:04 已关闭计划；权威 last_run 更新为本次 Cron。Occurrence、attempt、InvestigationRun、running、unknown、canary 均为 0，外部副作用为 0。

## 结论和下一波

本波证明 Q 的安装、授权、十路分发、Policy12、真实 source call 和游标闭环可以无需开发者手接线运行；由于源数据本窗没有变化，尚未证明 ProductEvent → Occurrence → Case/Run 的正向链。

下一波不修改商城数据制造变化。先用真实 65 行快照与经营参谋方案形成可审计的业务计划候选和变化判定条件；同时建立低频自然观察，只有商城真实变化时才自动进入 ProductEvent/Occurrence/Case/Run。若现有产品支持“基线分析计划”作为正式业务触发，则走其审批与内部任务链，不手工写 Case/Run。
