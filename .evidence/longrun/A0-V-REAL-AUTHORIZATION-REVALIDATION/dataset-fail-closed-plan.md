# Dataset 持久化失败不发布成功缓存

基线 a73d612d。D1 FR-D1-1 要求真实持久化；现有 sink 先创建缓存及 success build，再分别吞掉 dataset/history 持久化异常。

改 ec_dataset_sink.py：先完成既有两个持久化 Owner 调用，再创建缓存和成功 build；持久化异常包装固定 RuntimeError（不回传源数据/连接串），禁止返回 output_ref。add_build 失败也向上传播。不变更表结构、RID或租户语义。两个持久化事务之间仍可能部分完成，重试复用既有稳定 RID；不声称原子提交或完整幂等历史。

test_ec_d1_dataset_sink.py 显式隔离持久化 Owner，新增 dataset/history 两处失败测试，验证无缓存发布且固定错误。既有成功及空输入测试继续运行。后续处理持久化原子性与真实首链装配，不以本专项替代经营验证。
