# E17-s3o-w-ak：Provider 原 Store 插件批准门

## 上位方案与现时来源

`231-9` 首链要求真实能力/预算/审批后产物；AIP-7 §2 ProviderInstance 的唯一 owner 是 AIP-7，Provider 插件 manifest 为 Apollo/FDE 全局只读权威；R1-02/R1-03 必须以批准插件、Egress/DataClassification、opaque secretRef/version 签发不可变 Provider revision。BIND-1 不允许缺 Provider/Route/Eval 时制造 runnable。

现时原权威库 `aos_current_preview_20260927@a0v_135`、`org-org/dev-project` 的 ProviderInstance/RegisteredModel/ModelRoute/RuntimePolicy/ProviderHealth/Capacity 均 0。仓内 `ProviderPluginAuthority.get(org-org/dev-project,'agnes-text')` 返回批准 revision3、Owner `AOS/FDE`、exact hash；`dev-org/dev-project` 返回 `provider_plugin_scope_not_approved`。这些仅是全局插件批准，不是当前租户 ProviderInstance 或 Secret/Health/Route 正向。

`routers/aip_model_runtime.py::publish_provider` 先 `authority.validate_ref`，再调原 `AipModelRuntimeStore.publish_provider`；但 Store 本身只核 Egress/DataClassification，内部直接调用可绕过插件批准。原 `test_aip7_model_runtime_store.py` 的成功夹具用了 `test:plugin` 假 ref，暴露这个边界。

## 文件级方案与顺序

1. `services/aos-api/tests/aip/test_aip7_model_runtime_store.py`：在已有隔离 PG 真实 guard 签发后，先以未批准插件 ref 调原 Store，预期无 Provider/Receipt；RED 先证明当前会通过。随后使用现有 `ProviderPluginAuthority` 正租户批准 exact ref 保留原 CAS/重放/冲突正向。
2. `services/aos-api/aos_api/aip_model_runtime_store.py`：Provider Store 写入口在 guard/数据库写之前重用 `ProviderPluginAuthority.validate_ref(scope,item.plugin_ref)`；将稳定插件错误收敛成原 `ModelRuntimeDependencyBlocked`，不创建第二套插件真源。仅新增 Store 层保护，不改 DTO、HTTP、迁移、其它模型写路。
3. 专项加相邻 Provider API/Store 与 guard 测试，编译/差异复审；当前库只读、不发行 Provider、不启 Host/worker/Provider。若测试中有原隔离夹具需合法插件 ref，只改夹具，不降低新门。

退出界线：证明 Store 无法用假插件来源签发；隔离正向仍需要真批准插件与原 guard。不能把仓内插件批准、历史 Provider r7 或测试 secret 算作当前正式 ProviderInstance。
