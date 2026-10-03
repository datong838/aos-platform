# s3o-w-ag 独立切片｜Agent 激活时绑定现时性与事务锁

## 依据、现场与边界

- 231-9 首链要求六数字同事引用真实当前绑定；BIND-1 要求 active、可用/获准降级、新鲜且 exact 的 CapabilityBinding。当前 org-org/dev-project 六 Agent 均 provisioning，模板来源 Growth1.11，CapabilityBinding/ToolBinding 仍0；正式 BI OS/DB/IdP 身份本机均缺，s3o-w-ag 当前实例部分保持禁入。
- 原 `AipAgentInstanceActivationService.activate()` 先在独立连接读模板/绑定，再调用 `AipAgentRegistryStore.update_instance()` 的另一事务；前者通过后绑定可在后者提交前撤销，现有 Receipt 可能记录失去现时性的激活。只处理这个已存在的事务竞态，不造正式绑定，不放行当前实例。

## 文件级方案

1. `services/aos-api/tests/aip/test_aip_agent_instance_activation_current_binding_pg.py`：一次性 PG 库中用原 Store/Service 建合法 provisioning Agent+一条当前 Binding；在预检与原 update 之间确定性撤销，先 RED 证明旧代码仍激活。另验合法正向有原 `agent_instance.update` Receipt、跨租户/过期仍拒绝；current 库零写。
2. `services/aos-api/aos_api/aip_agent_registry_store.py`：`update_instance` 增仅内部可注入的同事务前置条件，在 idempotency replay 之后、CAS 更新之前执行；不改默认 Store 或公共 DTO。失败时无 Instance/Receipt 写入。
3. `services/aos-api/aos_api/aip_agent_instance_activation_service.py`：保留当前早期预检以维持调用契约，再于原 Store 事务内重查 exact published 模板和全部 Binding；`FOR SHARE` 锁住所读模板/绑定直至 Instance/Receipt 提交，禁止撤销并发穿透。重复同键只回原 Receipt；当前状态读取仍由原 Store CAS 保证。
4. 运行专项/相邻回归、真实隔离 PG 竞态正反、编译与方案一致性复审；写 verification，m1 精确提交及 AOS/Prime/D-wave 更新。无迁移、无当前库写入、Host/worker/Provider保持关闭。
