# BG-02 运行目录发现验证

基线f9783003。LivePreparedJobDirectory.current_targets返回脱离可变job的(scope,installation,generation)元组，最多1000，逐项校验登记key和当前jobidentity；不读业务表，不赋予Admission。原scope查询/注册/解绑不变。

RED缺方法；目录、原invoker及消费器装配30项通过（7条既有依赖警告）。AR2-7扫描1881/分类168/迁移93，各错误数组空；diff通过。未重启/部署/启动worker。下一步当前租户候选SQL与回绕扫描，原控制续期映射；游标只分配扫描顺序，不能作为业务消费ACK。
