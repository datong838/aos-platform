# W5CB4 BG-00be｜Quota 新 active 审批禁入

按 231/231-9 与 BG-00bb：QuotaPolicy 的 `approvalRef` 仅非空，Store 在无 maker/checker reader 时可直接发布新 active。当前正式审批来源缺失，实例继续禁入。本波仅在 `aip_model_governance_policy_store.py` 同请求幂等回读后阻断**新** Quota active；`routers/aip_model_governance_policies.py` 给 422 中文错误。Budget Policy 不在本波改变；历史 Quota 读取、草稿 CAS、幂等语义保留。

文件级 RED：`tests/aip/test_aip_model_governance_policy_store.py` 隔离临时 PG 证明字符串审批误受理，后断言拒绝无行；`tests/aip/test_aip_model_governance_policy_api.py` 验 HTTP 映射；需要历史 active 的模型依赖测试在 test-only PG 以单独既存行夹具核验，不能把该夹具当正式批准。专项/相邻、编译/diff 与方案一致性复审后落 verification、m1 精确提交、上下文和下波清单。当前库只读，Host/worker/Provider关闭。
