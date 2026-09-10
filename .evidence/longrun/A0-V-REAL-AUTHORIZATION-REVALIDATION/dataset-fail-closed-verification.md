# Dataset 持久化失败传播验证

2026-09-11，基线 a73d612d。移除先成功后吞异常行为：dataset/history 持久化完成后才 create_dataset/add_build，失败固定 DATASET_PERSISTENCE_FAILED，不输出内部异常；build 失败直接传播。稳定 RID、公开状态字段与租户参数不变。

两处持久化失败回归先红后绿，另验 build 失败传播，连同 OTWriter/预检共 31 通过，diff --check 通过。单测明确 mock 两个持久化 Owner，不隐含依赖不可用的默认数据库。既有 7 警告及退出 closed-stream 日志仍存在。

限制：无真实 PG 写入或上游调用；dataset 已提交而 history 失败仍可能部分写入，已有历史成功缓存不会被删除；build 失败时 dataset 缓存可能已存在。执行调用不会因这些失败返回成功，但不是原子回滚证明。API 未重载本修改。下一步 Owner 内原子 dataset/history 保存与恢复验证，再接真实数据业务链。不 push，230 L0 挂起。
