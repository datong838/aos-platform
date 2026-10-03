# E17-s3o-w-ao-b8｜正式 ToolDefinition 与独立发行合同方案

## 依据与当前事实

复习 231 首链/同制品约束、BIND-1 租户/CAS/幂等/Receipt 与 b5–b7 证据。当前四份签名 manifest 无 ToolDefinition；`UpsertToolBindingRequest` 只有 toolId、version、AgentInstance、状态、Capability/Policy 引用，没有签名 ToolDefinition exact ref、安装 epoch 或发行依据。`AipAssigneeResolutionStore.upsert_tool_binding` 以普通 `connect(scope)` 写 `aip_tool_binding` 并 commit，没有同事务 RegistryReceipt；HTTP 路由允许 admin/executor/aip_executor，后两类不能自动视为独立发行者。b6 两条 strict xfail 代表真实缺口。b7 已禁旧进程内 Tool HTTP 公开路由，不构成签名来源。

## 文件级实施顺序与退出门

1. **签名来源合同**：在正式 bundle 制品/安装方案中冻结 ToolDefinition 的 canonical 字段、content hash、签名链、sourceRef、tenant/install epoch、Owner 批准及撤销语义；读取当前四制品并做隔离签名正反例。缺正式签名制品时不得造“当前正式 Tool”。计划涉及上位制品/公共 DTO，先复审协议，再改代码。
2. **发行身份与事务**：设计独立非 owner、非 runtime 的 Tool issuer DB 登录，最小 INSERT/UPDATE ToolBinding 与 exact operation RegistryReceipt 同一事务；普通 runtime 对两表均不得伪造发行。当前真库不做角色/ACL/migration 写。先在随机 test-only PG 证明独立角色、错租户、重复同键、版本冲突、故障回滚和 runtime 越权拒绝。
3. **应用入口**：在 `services/aos-api/aos_api/aip_assignee_resolution.py`、`aip_assignee_resolution_store.py`、`routers/aip_assignee_authority.py` 仅增精确来源校验/issuer 组合；保留 disabled 撤销和旧数据只读，不以一刀切禁用 active 作为正向通过。RED 使用现有 `tests/aip/test_e17_s3owaob6_tool_active_source_red.py` 与发行 Receipt strict xfail，先精确复现，再最小改动。
4. **验证与切换**：目标/相邻/累计回归、签名制品+隔离 PG 正反链、OpenAPI/DTO drift；当前生产启用须外部正式签名来源、私有凭据、独立备份完整恢复和零执行窗口全部通过。当前真库只读，Host/worker/Provider关；浏览器仅在有用户可见变化时复验。

## 可并行的已授权安全切片

当前 ToolDefinition 来源为空，因此先继续 D-waves 已列的 Provider/Eval/License 或 Reader 身份链独立代码项。下一个文件级调查先核 `aip_assignee_resolution_store.py` 的普通 runtime 发行权限与现有签名制品合同，形成隔离 RED；公共协议未复审前不做生产发行正向、不扩大权限。Goal active，m1单写、不 push；org-org/dev-project 唯一正向，dev-org 零副作用，不读商城源、不重放旧12 Run、不手工 Run、不碰230 L0。
