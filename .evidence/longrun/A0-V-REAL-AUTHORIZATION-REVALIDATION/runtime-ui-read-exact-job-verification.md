# UQ3-E 共享门禁与精确实例验证

2026-09-13，基线772200b0。API门禁机械提取require_current_catalog_read，供具体宿主准备/完成前复用；返回资源条目不授执行权。CurrentInstalledPackageInvoker新增可选expected_job：构造必须当前目录的真实实例，IPC前后必须同一对象，原调用未传参数保持原行为。

28 passed、7项既有warning：15项invoker（含3项新增实例前/中替换）+13项API非超级PG门禁。调用前替换为零invoke，调用期间替换结果被拒绝，正确实例成功。此处invoke为协议测试替身，不代表新只读方法已在OCI交付。AR2扫描1844模块、163分类、93迁移，各错误集合为空。

未触及主库或原运行实例。下一波具体UiReadConsumer：独立受限事务，当前身份与目录，canonical快照/claim同事务，原实例IPC事务外，完成前再验当前事实；再接Host assignment撤销和关闭恢复。自然经营首链与八场景尚未完成。
