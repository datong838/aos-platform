# 占用根与首事件不可变验证复审

仅新增独立测试证据，产品 HEAD40301f6e工件逐字保持，默认迁移/真库/旧保留库不修改。

R1真实失败20.42秒：根单表TRUNCATE由原外键先拒绝0A000。独立六张准备表为零、临时探针零。修正测试为明确根+事件两表TRUNCATE，不用CASCADE，不改产品约束和原Judge50秒有效期。

R2完整原Source/SCRAM/正式独立双批准/四腿计划/真实Target Intent/call/root/首事件原生回归1PASS97.47秒。实际Owner窄测试探针分别UPDATE/DELETE两表42501；已有待提交事件下TRUNCATE55006；空根+事件及单事件TRUNCATE自定义门42501。六次savepoint后原完整记录与hash精确不变。临时探针只在新独立全库安装，原NOLOGIN Owner/fixedsearch_path/revokePUBLIC，并实际清除。实际callerCOMMIT仍拒绝23514。

独立只读连接验证xid aborted、六表零、Source1、Owner无LOGIN/成员、临时探针零、窄准备入口已移除；31个原资源的身份、启动时间、卷与端口不变。本轮没有产品变化，上一轮318纯测试无需机械重复；此次完整原生相邻回归为实际证据。

局部测试预期差异已修复，不影响主线和Goal。真实准入、费用分配、状态转换/unknown持久占用、finalizer/最终COMMIT期限、Target结果和Judge输入仍未完成。五个父任务保持ACTIVE。下一步骤已调查并登记：严格非执行根/首事件类型契约，禁止把awaiting_target_result的Judge依赖伪装为完整运行输入。浏览器不适用于未接运行入口artifact。
