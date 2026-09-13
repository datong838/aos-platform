# UQ3-I 当前安装读取范围验证

基线9b6aef11，m1单写；不push，230 L0挂起。

## 结果

当前签名目录仅呈现模块所需dataScopes均由当前CompositionLock target授予的条目。API入队及宿主prepare/finish原有fresh catalog门禁继承此约束。原安装调用器可选required_data_scopes，UI消费者从签名模块传入，读取canonical快照之前验证当前安装、包hash及范围，IPC前后重复核验。旧调用默认空范围及原快照合同保持不变。

新增测试先复现6失败/38通过；实现后44通过。HTTP/入队/原Host/生产装配回归34通过，均7项已有warning。缺scope零IPC，中途撤销不交付不重试；真实PG消费者拒绝路径无快照、无Attempt。目录锁与安装baseline使用受控测试替身，非真实租户授权证明；未安装后继包或调用实际OCI。

AR2扫描1846模块、163分类、93迁移，hash/依赖/跨层/动态引用错误均为空；git diff --check通过。

## 未完成与接续

主库仍030、API/原宿主未升级，真实安装授权并未变更。UQ4需专用受限结果查询函数、当前主体与资源重验及HTTP/Web等待；UQ5后继签名UI和只读方法；UQ6实际安装升级与读取；UQ7首链八场景观察。测试绿不代表真实经营闭环。
