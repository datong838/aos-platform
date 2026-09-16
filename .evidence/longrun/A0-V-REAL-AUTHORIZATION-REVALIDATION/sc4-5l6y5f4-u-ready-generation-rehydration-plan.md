# SC4-5L6Y5F4 U：当前就绪代宿主冷启动接管方案

日期：2026-09-17

## 问题与现场事实

独立 Runtime Host 只从未交付的 `runtime-apply` outbox 创建进程内 `PreparedJob`。一旦宿主进程重启，已交付且已成功的当前代不会再次进入目录；业务 worker 因而没有 live target。2026-09-17 真实 L 现场进一步证明：旧租约过期后恢复器正确把 binding 栅栏为 `enabled=false / operation_fence=true / observed_state=unknown`，三个资源均 `released=true`。该状态禁止原地复活，后续必须创建新代。

## 本波范围

本波仅补齐仍处于合法接管窗口的当前就绪代：安装 active、binding `ready/enabled/unfenced`、原 `runtime-apply` 已成功、全部签名资源仍为 pending/unreleased、租约未过期、容器与 claims 精确一致。宿主在同一事务中重验当前安装锁、权限、运行条件、签名 claims 与资源集合，续 180 秒短租约并记录接管事件；随后只重新附着原容器并重建签名 IPC 会话。

接管不调用 `claim_preparation`，不创建新 generation/resource，不重复 `preparation_committed`、verify、configure 或 enable，不制造 outbox。任一身份或时效不符均失败关闭；过期/释放/unknown/fenced 状态仍由既有恢复器与后续新代重建处理。

## 代码路径

- `extension_runtime/preparation_plan.py`：新增当前就绪代接管计划，只读当前权威并原子续租。
- `extension_runtime/oci_driver.py`、`session_supervisor.py`、`journaled_session.py`、`signed_session.py`：按持久化 container/name/owner 精确附着；关闭仍走原资源日志。
- `extension_runtime/preparation_worker.py`：构造恢复 `PreparedJob`，禁用 verify/enable 重放，只保留健康与续租。
- `extension_runtime/pending_preparation_directory.py`、`preparation_consumer.py`：目录同时返回 pending 与可接管 ready，二者使用明确 mode；同一安装不得出现歧义。
- 对应 `tests/extension_runtime/`：目录、计划、worker、OCI 命令、取消与负状态。

## 退出条件

1. pending 首次准备行为不变；ready 接管不消费/伪造 outbox。
2. 接管前所有 current/tenant/signature/resource/deadline 守卫通过；失败零 OCI 启动。
3. 原 container 精确附着、注册和 heartbeat 成功后进入唯一 live directory；关闭精确释放。
4. expired/released/unknown/fenced/cross-tenant/claims drift 全部拒绝。
5. 定向与邻接测试、方案一致性、diff 检查通过并提交。

下一波 V：对当前已释放且被栅栏的 L 执行新 generation 受控重建，恢复配置与 enable，再重新开启一条短时真实自然商品任务，验证 ingress 自然进入 occurrence/Case/Run。
