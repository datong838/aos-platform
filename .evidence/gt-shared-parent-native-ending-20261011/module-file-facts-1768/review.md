Rules：231、原Task Lease、方案先行、m1单写。
新增接口仅返回当前磁盘字节事实；两次loader路径对账，逐文件descriptor前后stat和路径身份复核，256MiB上限，取消响应，PG异常释放hash/文件。实际编译Werror已通过；7项原生测试通过，包括权限、独立SHA/stat、副本变化、超限拒绝及错误后恢复、原有4项相邻逻辑。原pending和paths正文精确保留。
仍不证明映射页来源、跨文件原子快照、不可变安装、完整回调闭合或正式执行权限。新接口仅隔离事务内安装，回滚后不存在。完整Task保持ACTIVE，不出Delivery。
观察器因checkpoint包含.c/control/Makefile被当前suffix过滤拒绝，未伪造通过，下一步在独立机制合同中修复。
