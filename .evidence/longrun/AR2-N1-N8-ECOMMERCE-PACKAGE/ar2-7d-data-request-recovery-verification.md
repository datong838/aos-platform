# AR2-7D D1 数据请求与完整回执恢复切片

日期：2026-09-08。父任务：AR2-HOST-WIRING-CUTOVER-PLUGGABILITY-BROWSER-ACCEPTANCE。
仍为 AR2-7D 第3/8步，不推进完整波次 GREEN 或业务场景完成数。

## 已实现

- 请求宿主调用现有 DataCommand/Saga，同事务复用公共 Store；不复制领域权威。
- 完整原请求优先读取原 requirement 与 Run 状态回执，不依赖已变化的当前 checkpoint／PAUSED 状态。
- 历史 requirement 精确引用回读校验租户、版本和重算正文哈希。
- 新 ar2_008 保留完整履约 authority；保留原时区、blockers，旧无 payload 记录不补造。
- 受限数据库入口严格校验完整 JSON、引用、规范时间、哈希、幂等键与当前 requirement。
- 数据库反例使用独立标识，核验 DF001 与未占幂等键，排除重复主键假通过。

## 新鲜验证

1. test_data_fulfillment_store.py、test_data_requirement_store.py、
   extension_runtime/test_ecommerce_data_request_host.py、
   extension_runtime/test_ecommerce_niushop_data_fulfillment.py：51 passed / 17.35s。
2. test_aip_business_investigation_fulfillment_saga.py、
   test_ecommerce_business_investigation_data_command.py、
   extension_runtime/test_ecommerce_growth_runtime_adapters.py：37 passed / 6.00s。
3. 独立 Prime 只读复审 PASS：请求恢复、精确读取、完整履约序列化及哈希回读。
4. 代码 diff whitespace 检查通过。仅一次性隔离 PostgreSQL 迁移与测试，无共享库迁移。

## 边界与继续入口

尚未注册完整 DataFulfill 生产服务；未声称真实业务已履约或浏览器已验收。
未调用付费 Provider，未修改真实业务数据，未发布外部内容。
下一切片：Observation／Hydration 原 authority 精确回读与数据履约绑定，继续同一 AR2-7D 波次。
