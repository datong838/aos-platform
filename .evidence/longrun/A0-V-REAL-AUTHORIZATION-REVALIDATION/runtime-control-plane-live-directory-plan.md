# Runtime control plane 唯一 live directory 方案

日期：2026-09-12

基线：`dce4bbeb`

## 合同

`RuntimeControlPlane` 新增进程所有的 `LivePreparedJobDirectory`。正式
`build_runtime_control_plane` 每次构造恰好创建一个目录；同一 control plane 的 lifecycle、未来 runtime
worker 与 stage-review composition 必须复用该实例。构造仍是纯 wiring，不连接数据库、不启动 OCI、
不登记 job。

保留 dataclass 测试/选择器使用的显式兼容缺省，但 production builder 返回值必须是 concrete directory。
目录存在不代表 runtime host active、Installation ready 或 package 可调用。

## 文件与验收

- 修改 `services/aos-api/aos_api/asset_registry/control_wiring.py`。
- 扩充 `services/aos-api/tests/extension_runtime/test_production_runtime.py` 与 startup composition 测试。
- 新增本波 files/verification，更新 closure。

验收 production build 只创建一个空目录、两次 build 不共享、app state 保留该对象、构造零运行副作用。
下一波实现由该 control plane 所有的 preparation orchestration。
