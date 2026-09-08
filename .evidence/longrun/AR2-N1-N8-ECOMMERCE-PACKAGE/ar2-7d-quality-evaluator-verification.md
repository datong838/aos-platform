# AR2-7D D1 质量与人口判定切片

- 基线：代码 d6371b38；authority AOS-000571；沿用 AR2-HOST-WIRING-CUTOVER-PLUGGABILITY-BROWSER-ACCEPTANCE Task/Lease，不推进整波 GREEN。
- 文件：aos_api/data_requirement_quality.py、tests/test_data_requirement_quality.py；方案 231-6 第1节真实履约质量施工卡。
- Red：新增测试因模块不存在失败。实现后首轮20通过、1失败，失败是测试修改有效期未同步权威哈希；修复fixture并增加边界反例。
- 最终命令：PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_data_requirement_quality.py services/aos-api/tests/test_source_readiness_contracts.py services/aos-api/tests/test_source_readiness_investigation_projection.py -q --tb=short --show-capture=no
- 输出：31 passed, 8 warnings in 11.89s。警告为既有schema命名/测试客户端弃用及故意非法计数序列化；无业务访问。
- 独立Prime只读复核PASS；指出grain与人口单位不能等同，已改为独立解析的版本化策略输入，并验证day/customer反例。
- 新逻辑：逐事实精确阈值、零分母不通过、独立人口总数、严格整数、完整范围、需求哈希、最早源时间及有效期交集；无SQL、无调用外部服务、无页面变更。
- 边界：本函数不能认证调用者自报测量，也不产生履约。Host仍须独立读取策略与源引用，固定查询生成真实测量；Evidence保存与完整DataFulfill尚在施工。
- 下一施工项：复用aip_evidence同事务持久化质量证据，再接固定查询与履约。整波累计回归、浏览器与CAS仍在后续门。
