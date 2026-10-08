# 保留隔离库测试入口数据保护方案

基线 m1 eb982a9d3d2184a0c4b403b6561d6410c09dfbe5，AOS-001594；按231方案先行/Task Lease/RED/最小修改/专项/相邻/复审/证据闭环。

实际失败：Source joint fixture r1 在原 ProviderCapacity Action Guard 读取元数据时拒绝；只读核对原库965@158发现对象定义已缺失、Action定义仍正确、registry/publication均零、原申请1。a146原迁移安装正确定义，tests/conftest.py client 的全局DELETE谓词会删除该定义；数据损失发生路径已定位，但未宣称该DELETE是唯一历史原因。保留原申请，不重发发行。

候选1（本轮）：已授权隔离测试保护，确切Task scope conftest.py/专项测试/本目录，无其他Lease重叠；依赖原保留库环境开关，禁止在保留模式清理历史对象/元数据。候选2：原Source物理账户与两父共同占额继续；依赖完整原元数据安装和原注册空域，本轮先排除测试入口破坏，不能直接覆盖保留库定义。新Judge全链仍待验收。

实现：抽取原两条ontology cleanup到一个函数；AOS_TEST_RETAIN_DATABASE严格等于1时返回，其余模式仍原SQL且一次commit。只用于测试client，没有生产代码、迁移、数据库写入或审批Guard变更。新函数不能更改环境变量，不引入自动恢复或伪造Source事实。

验证：先用专项测试调用预期函数得到缺失入口RED，再实现；覆盖保留模式零execute/commit，普通默认及0/其他值仍原清理，SQL故障传播不commit。对原client调用位置做结构核对，Python编译。真实失败库只读保存原状态，不以单测当Source组合成功。风险：保留模式历史数据可能影响旧空态假设，须独立唯一输入和原门禁；不自动修复已损坏元数据，不宣称所有旧测试绿色。回滚只回退本次函数抽取和调用，保留历史证据及数据。
