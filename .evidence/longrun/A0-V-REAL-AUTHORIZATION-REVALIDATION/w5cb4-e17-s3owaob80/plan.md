# b80 正式evaluator整体方案与现有事务接缝复验

基线821109b3/权威1329。只evidence，复习实际for_transaction与b45 PG tests、Resolver读源与原BIND-1§5；不重复创造事务factory。先形成准确全依赖命令顺序/锁与初始化门/具体文件；真实一次性PG复验已有同事务能力，不能用2tests冒称全evaluator通过。当前135真库不写、私有凭证不读；阶段设计兼容普通preview/证据功能。
