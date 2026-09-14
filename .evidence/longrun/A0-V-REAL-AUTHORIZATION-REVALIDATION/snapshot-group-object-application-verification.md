# 组对象原链路应用验证

SC4-5h1：ControlledSnapshotGroupObjectExecutor 完成。先独立提交关系准备并确认退出，再按原控制顺序调用 ControlledSnapshotExecutor.resume_saved，复用真实 ConsistencyStore、派生准备、Projector 与 dataset Receipt。阶段间复验整组当前准备，最后逐原 command 重核当前权威对象、outbox 和投影，全部 pending=0 才返回对象阶段完成。

9 项完整 PostgreSQL 回归通过，14.95 秒（新 5 项和原单表 4 项）。Shop+Weapp 两成员产生 2 份权威对象/Receipt/投影对象/数据集/历史记录，运行仍 running，关系写入 0。第一次成员完成后中断可重放首成员并续跑第二，源调用保持一次；准备 commit ack 丢失不开始应用。历史数据集成功但权威对象已被原 Store 更新时，最终拒绝旧组结果。

AR2 扫描 1920 模块，五类错误为空。测试表为完整隔离 PG schema，源和发行资产仍是明确 fixture；主数据/安装未改变。对象阶段是逐成员可恢复提交，不声称整组对象原子事务，也不宣告整组 Readiness 或 Fulfillment。

下一项：严格关系写入模式，拒绝悬挂或被新版本覆盖的关系，保留原通用写入行为；随后固定关系命令准备、提交确认、实际应用及 Receipt/投影核验。
