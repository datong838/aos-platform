# AR1-a 静态合同交付证据

基线 m1@36942b23。无数据库迁移、容器启动、Provider调用、业务数据写入、UI改动。浏览器 N/A（231-8冻结范围）。

改动前测试先出现测试文件语法错误，修正后得到目标模块不存在的失败，再实施生产模块；不把测试自身错误当功能缺陷。新增声明25项先通过，邻接130项、补签名篡改131项、扩展release policy/canonical最终169项通过。

最终命令：`PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest --noconftest services/aos-api/tests/extension_runtime services/aos-api/tests/asset_registry/test_manifest_contracts.py services/aos-api/tests/asset_registry/test_manifest_loader.py services/aos-api/tests/asset_registry/test_signature.py services/aos-api/tests/asset_registry/test_installation_service.py services/aos-api/tests/asset_registry/test_installation_revalidation.py services/aos-api/tests/asset_registry/test_release_policy.py services/aos-api/tests/asset_registry/test_canonical_hash.py -q`

本次结果169 passed、6条既有模型字段告警，7.06秒；退出时既有JDBC清理logger打印closed stream错误，缓存0/0，pytest退出0。不声称全仓日志无异常；本次未修改该日志模块。`--noconftest`避免根自动数据库fixture，选中测试均为纯函数/临时文件/mock事务。

改动前loader取得growth/1.3.0摘要acd2590090a731fd3fa4ed00833ebc09a64832fe88ee7b00855c4cd8c0968bbf，operations-base/1.1.0摘要bc4a8bcf6105363bae2ec3099947d5951ec7b65ae84214e475c9457f8ab9c04f；新实现回读相等。现有包无签名evidence；隔离Ed25519 fixture验证runtime有效签名和声明改变失效。

独立Prime增量只读复审通过，未独立重复执行测试。apply/verify都经过共有revalidation保护；暂沿用409，专用生命周期错误/UI入口归AR1-c/d。不产生runtime binding或物理可插拔完成结论，业务闭环新增0。

下一包AR1-b：隔离制品、IPC、监督器与真实OCI反证；先核验隔离环境，后续持久权威接入前业务ports关闭。
