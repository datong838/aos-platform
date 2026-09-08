# AR2-7D D1 质量 Evidence 持久化切片

- 基线50a741ea；仍为AOS-000571／同一AR2-7D Task/Lease；不推进整波GREEN。
- 方案231-6质量证据施工卡；新增data_requirement_quality_evidence.py及同名test文件；复用aip_evidence，无新迁移或公开路由。
- Red：模块缺失导致collection失败。实现后首次显式选备用测试端口因缺既有aos_app角色，隔离库启动失败；未创建共享角色或改共享库。恢复仓库标准隔离测试入口后通过（fixture每次创建并销毁独立数据库）。
- 最终专项/相邻累计命令：PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_data_requirement_quality_evidence.py services/aos-api/tests/test_data_requirement_quality.py services/aos-api/tests/test_source_readiness_receipt_store.py services/aos-api/tests/test_aip_business_investigation_fulfillment_saga.py -q --tb=short --show-capture=no --disable-warnings
- 结果56 passed,8 warnings in18.52s。隔离真实PG验证同内容并发去重、回滚、canary和撤销；单元验证正文/拆列漂移、原需求时区和质量不充当事实覆盖。
- 独立Prime只读PASS；本切片无真实业务数据写入、外部调用和页面更改。
- 硬边界：内容地址去重不是业务幂等；Host重放必须恢复原评估时刻，实际履约前复验当前时效、撤销与源权威。固定factIds=[]，测量不能替代真实事实Evidence。
- 继续进入固定查询Owner／精确源谱系接线，DataFulfill仍未注册为完整生产能力。D1–D4整波验收、Delivery Receipt、CAS保持原门。
