# W5c7u Snapshot worker 可选 lease 传递 verification

方案 `15ff1953` 先于代码 `05a5530b`。文件仅改 `services/aos-api/aos_api/pipeline_control_service.py` 与 `services/aos-api/tests/test_pipeline_control_service.py`；新审计见同目录 `w5c7u-snapshot-worker-lease-propagation-audit-20260925.md`。红测先得到“unexpected keyword argument host_lease”，绿测证明默认 None、同一 exact 对象传入两个 runtime、错误类型与 dev-org 跨租户在连接前拒绝。

专项工厂测试 **7 passed**；包含近期 A0-V no-effect 与 main lifecycle 的累计 **237 passed**、7 warnings/18.75 秒。`git diff --check` 通过；临时测试 DB **0**，既有测试 PostgreSQL 停回原态。浏览器 5174 只读核对 2026/9/25 18:29:55 CST：A0-V Canonical rev4「已停用」「数据组已停用」；待同步写操作 1 未冲刷，未点击任何写入/执行，临时 Vite 与页面已关闭。

真实 closure 只读门仍 `automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、12 原 Run running、stalled Receipt 0；缺全机拓扑、Fresh Owner 同事务门、独立 closure 方案/key。复审确认 `main.py` 未注入 lease，Runtime Host flag 默认 off，真实 DB/Host 未变。不能把这次接口测试称为 worker 全覆盖或 closure 授权。商城源行未读、230 L0 挂起、dev-org 仅零 canary、m1 不 push。

下一波 **W5c7v**：先方案后盘点独立 Schedule worker、A0-V Host 三业务 worker 和 PipelineControlServices Owner 写路径的 lease/fence 接入矩阵；发现可安全局部修复的缺口才做隔离 Red-Green，真实 opt-in/迁移仍冻结。
