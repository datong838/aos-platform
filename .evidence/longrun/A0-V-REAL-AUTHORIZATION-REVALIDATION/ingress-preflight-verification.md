# Dataset 前规范输出校验验证

2026-09-11，基线 d7a8dfae。真实 ec_live_executor 在 Dataset 前调用无 I/O 的 validate_ot_output，复用原 OT 构造校验。新 2 项先红后绿，与原 OTWriter 19 项共 21 通过；git diff --check 通过。既有 7 警告及退出 closed-stream 日志问题仍在。

用例对源、transform及外部写入做隔离，证明缺类型/缺必需字段时两个 sink 都不调用。不是 PG/上游实测，不代表全部异常下的原子性；规范化校验执行两次（预检与写入自身），保留其他调用者保护。Dataset 当前吞持久化异常仍须修复；真实配置缺失和首链装配未完成。API 未重载本修改，无真实业务执行，不 push，230 L0 挂起。
