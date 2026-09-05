# AR1-c 查询校验内部检查点

日期：2026-09-06（上海）；主线 m1；不是整波交付。

- 新增 PostgreSQL AST 白名单校验、摘要绑定、int8/text/bool 严格参数校验。
- 新增物理关系和内建列类型校验原语；隔离 PostgreSQL 中验证继承、类型错、自定义 domain 拒绝。
- pglast 固定 8.4；uv.lock 仅新增此依赖，存量包不升级。
- 红灯：缺少 query_registry 模块、validate_parameter、require_registry_relation 的测试先失败；实现后绿灯。
- 新查询专项39项；累计295 passed / 6已有warnings / 35.67秒 / exit0。累计包含专用OCI与专用PG测试。
- 已有 JDBC 退出日志 closed stream 报错仍存在，缓存计数0；未宣称零告警。
- Prime 首轮只读复核未发现 AST 直接绕过；继承与自定义运算类型风险已纳入方案。关系元数据增量复核因模型容量重试中。
- 没有新增页面；本切片浏览器验收不适用。AR1-d 页面尚未交付。
- 限制：未完成签名 query registry 接纳、受控查询执行端、命令端、安装激活和全生命周期封板；业务场景新增0。
- 下一工作：同一 AR1-c 内继续受控执行与签名接线，不自动转入 AR1-d。

累计命令：AOS_EXTENSION_OCI_TEST=1 AOS_EXTENSION_PG_TEST=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest --noconftest services/aos-api/tests/extension_runtime services/aos-api/tests/asset_registry/test_manifest_contracts.py services/aos-api/tests/asset_registry/test_manifest_loader.py services/aos-api/tests/asset_registry/test_signature.py services/aos-api/tests/asset_registry/test_installation_service.py services/aos-api/tests/asset_registry/test_installation_revalidation.py services/aos-api/tests/asset_registry/test_release_policy.py services/aos-api/tests/asset_registry/test_canonical_hash.py services/aos-api/tests/asset_registry/test_control_wiring.py -q
