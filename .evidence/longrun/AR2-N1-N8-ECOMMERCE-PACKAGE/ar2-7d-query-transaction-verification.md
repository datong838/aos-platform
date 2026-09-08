# AR2-7D D1 QueryResult同事务与精确历史回读

- 基线c035a56e，AOS-000571；同一AR2-7D Task/Lease继续，整波未完成。
- 文件aip_analyst_query_store.py、tests/test_aip_analyst_query_host_transaction.py；施工卡231-6。
- Red：2项测试因Store不支持连接／时钟注入失败。实现保持默认行为，Host复用既有TransactionBoundConnectFactory，所有提交控制归宿主。
- 最终命令：PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_aip_analyst_query_host_transaction.py services/aos-api/tests/aip/test_aip8_query_store.py services/aos-api/tests/aip/test_w_l17_async_jobs.py services/aos-api/tests/test_aip_analyst_query.py -q --tb=short --show-capture=no --disable-warnings
- 结果21 passed,7 warnings in21.35s。数据库为仓库测试fixture创建销毁的一次性库，未写真实业务数据。覆盖全事务回滚、历史结果在job推进后可读、canary、错误修订/哈希/manifest/拆列及原HTTP回归。
- Prime独立只读代码PASS；注意原hash不覆盖完整DTO：confidence/blockers不可用作新质量或履约授权。未声称完整正文防篡改，未改旧hash算法。
- memory-status全部强一致CURRENT，memory-validate GREEN，projectRevision AOS-000571，865 Delivery／846 Task；不以测试数冒充完整业务闭合。
- 下一项：显式canonical-query测量来源分支，随后固定全集统计与真实事实Evidence。旧展示页结果不可作为完整人口分母。
