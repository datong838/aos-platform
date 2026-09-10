# 接入批次不静默丢行验证

2026-09-11，基线 df789e2c。缺失/空 ot 或空 link_type 现在抛固定 OT_OUTPUT_ROW_TYPE_REQUIRED，无源内容泄漏；空批次与合法记录保持既有行为。无效混合批次不会调用 checkpoint 或 apply_batch。

新回归 6 项先失败，修复后 OTWriter 全 19 项通过。扩展执行器两文件 26 通过、3 失败：OperationalError 数据库连接失败；在独立 Python 进程加载 git HEAD 旧 OTWriter 后复跑，同样 26 通过、相同 3 失败。未修改工作树回滚，也未把环境失败标绿。git diff --check 通过。既有 7 警告和退出日志 closed-stream 错误仍存在。

范围：只验证内存 store 调用合同，无真实源或数据库写入。执行器先写 Dataset 再写 OT，故此修复仅保证 OT/断点边界，未证明 Dataset 与 OT 原子恢复。下一步检查执行器预校验/失败恢复以及实际来源输入装配。API 尚未加载本轮修复；业务执行器仍关闭。完整首链、八工作台未完成，不 push，230 L0 挂起。
