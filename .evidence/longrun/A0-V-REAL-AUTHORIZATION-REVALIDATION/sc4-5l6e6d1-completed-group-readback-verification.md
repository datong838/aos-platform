# SC4-5l6e6d1 完整组完成态回执只读验证

日期：2026-09-15
基线：`a87ddc0ce3984db95674d0e022feb73490f42f97`（m1 / AOS-000573）

## 交付范围

本切片为原 Relationship、LinkCommand、RelationshipAudit、Retirement 四层不可变回执增加完成态只读入口，并修正十二成员完整组在同一 Assessment 内重复进入完整组政策守卫导致的调用栈耗尽。Assessment 仍由原 Input 持有十二成员 current/claim 锁，继续使用原安装政策 loader，并在消费前后重读政策；没有扩大权限、缩短完整组、提高递归上限或接受调用方提供的合格结论。

完成态入口只能读取已经存在的原回执。`prepare` 仍要求运行态；完成态读取缺失原记录时失败，不补写 Relationship、LinkCommand 或 Retirement。所有读取仍核对 exact 策略、十二路输入、对象投影、链接/清退 Store Receipt、hash、租户与回调前后当前性。

## Red 与修复

首次把完整十二路 Retirement→Audit→Link→Relationship→Assessment 串联时，Assessment 每层再次进入同一完整组策略/current 守卫，实际触发 `RecursionError: maximum recursion depth exceeded`，用例在完成态断言前终止。修复只消除 Assessment 内重复的相同完整组守卫帧，保留外层 Input 完整组锁、原 `_load` 和前后策略复验。

## 新鲜验证

- `test_analysis_snapshot_completed_readback_pg.py`：`2 passed, 7 warnings in 136.37s`。覆盖无需清退和实际非空条件清退；后者建立历史旧父边、执行原 Retirement 与投影，确认剩余链接/图边、非空命令及 applied Receipt，并验证完成态重复读取不增加任何回执或源调用。
- Assessment、Relationship、LinkCommand、Audit、Retirement Journal/Executor 六组相邻 PostgreSQL 回归：`66 passed, 7 warnings in 190.63s`。
- `git diff --check` 通过。
- `verify_closure.py --phase ar2-7`：`1951 scanned / 192 classified / 93 migrated`，`hashErrors`、正向/反向未分类依赖、跨层导入和动态引用错误均为空。默认 `ar2-0` 会把后续 A0-V 合法演进当作历史哈希漂移，本次以权威阶段 `ar2-7` 为准。

系统重启后 Docker 服务和 18432 隔离测试库均未运行；本轮恢复 Docker，并重建带原约束角色的 `aos-extension-pg` 隔离库后生成上述证据。该环境恢复不涉及真实商城数据库。

## 边界与下一步

本切片没有迁移主库、读取真实商城、调用模型、创建真实 Task、安装或发布；测试里的调度终态仍明确是完成态只读 fixture，不能作为统一调度收尾或真实经营首链证明。用户现有 `overall-progress-20260913.md`、`package.json`、`package-lock.json` 改动保持未暂存；不 push，230 L0 继续挂起。

下一切片 e6d2 按既有方案新增固定完整组完成服务，并最小抽取原调度结果写入职责：全 running 才执行原恢复链，全 succeeded/stopped 只读回放，混合或未知状态拒绝；十二路终态同一元数据事务 CAS，后验失败整体回滚，独立 Store 效果依原幂等 Receipt 恢复。
