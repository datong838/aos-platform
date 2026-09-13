# 当前运行状态下的路由 UI 只读接口验证

基线 26bbe4b8，按 runtime-workshop-ui-http-plan.md 实施。

- RuntimeViewReader 接收可选 requested_route，仅 current ready 且 binding 存在时传给原签名 resolver；停用/封锁不解析 UI。旧无参数调用保持旧形状。
- 原 GET runtime installation 增加可选 route，不接受客户端租户/代次/权限；空、超长、不规范、重复路径固定 422 提示并在 reader 前拒绝。避开全局校验默认 400 的差异，不修改全局行为。
- RED 8 failed；第一轮 37 passed /2 failed（空和超长由全局处理器变 400）；最小调整后 39 passed，7 条现有依赖警告。
- AR2 扫描未新增模块，1831/159/93，五类错误为空；项目强一致投影 CURRENT。

本文件记录代码验证，尚不是主库 UI 交付证据。随后受控重载 API，再请求真实 ready 安装的 route 查询；因当前签名包均无 frontend，预期 ui=null。不能把此空结果称为八工作台已完成。
