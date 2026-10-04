# b65 文件级方案：普通评估禁入与回执配对

## 已复习的依据

- 231-3、BIND-1 的当前签名安装与可信依赖判据；b22/b44/b46 的受限身份与回执边界；b64 已把普通 Capability issuer 缩至生命周期五列。
- `aip_capability_binding_service.py:evaluate` 先 `get` 和独立 Reader 预计算，最后才用普通 issuer UPDATE 多个 readiness 列；当前失败表现为持久化异常，可能映射成 503。
- `routers/aip_bindings.py` 将 `AipAgentRegistryConflict` 映射 409；`aip6_002_registry_receipts.py` 的共享 Receipt 表目前仅 append-only、租户 RLS，没有按 operation 限制普通 issuer 写 `capability_binding.evaluate`。

## 本波最小改动

1. 在原 Service 的 `evaluate` 入口、任何读库/预计算之前，识别原生产装配使用的 `RegistryIssuerConnectionFactory(command_family="capability_lifecycle")`，抛出专用 Conflict 子类，返回明确 409 `AIP_BINDING_EVALUATOR_REQUIRED`。旧默认/测试服务行为不改；普通 create、revoke 保留。
2. 先加隔离 RED：签名夹具下普通 issuer 直接插入 evaluate Receipt 仍成功，证明共享表 operation 尚未受保护。RED 不写当前库，不把伪回执当业务成功。此缺口需要后续唯一正式迁移与可信 evaluator 事务一起解决，避免本波即兴改共享全局 Trigger 破坏其他命令。
3. 专项验证入口无 Reader/Issuer 调用、HTTP 409、Binding/Receipt 无写、create/update 正向；相邻 API/PG 回归。计划、RED、代码、验证与上下文逐项落盘。

## 安全边界与后续

当前真实库只读；不启动 Host/worker/Provider，不读取商城源、不回放旧 Run、不手工 Run。Receipt operation guard、同事务八依赖、签名 Installation/Registry 锁、正式独立 evaluator 与唯一136 属后续波；在这些完成前 available 仍不得放通。
