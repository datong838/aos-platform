# W5CB4 BG-00ba｜网络 active 发布审批失败封闭

## Rules 与方案复习

231-9 BG-00 需要产品内正式配置恢复，231 总计划不授权仅凭审批字符串执行安装激活。BG-00az 证实 `NetworkPolicyRevisionCreate.approval_ref` 仅非空，Store 在校验当前 Egress 后直接写 active Revision/Receipt；尚无可消费的网络审批权威。按最小安全修复，正式来源缺席时阻断**新** active 发布，保留已有记录的只读消费和同请求幂等回读、非 active 草稿提交；不假造批准或开放环境开关。

## 文件级 RED/实现

1. `services/aos-api/tests/aip/test_aip_network_policy_store.py`：先增加 test-only PG RED，证明 `approval:test` 不能创建新 active；验证草稿仍可写、幂等回读不退化。现有依赖 active 的测试按历史读取场景处理，不以 mock 权威当正式通过。
2. `services/aos-api/aos_api/aip_network_policy_store.py`：在幂等旧 Receipt 回读后、写入前拒绝新 active，使用专用错误码。未来正式审批 reader 在同事务可消费前不可移除此门。
3. `services/aos-api/aos_api/routers/aip_runtime_guard_policies.py`：映射专用 422 错误，避免通用 503；不暴露敏感审批内容。
4. 运行专项和相邻回归，检查历史 active 读取合同、租户隔离、无当前库写入；验后记录 verification、m1 精确提交并更新 AOS 上下文。当前 Host/worker/Provider 继续关闭。
