# 数据健康读取失败不伪装为零数据

产品 API 已确认当前 user:dev 为 org-org/dev-project，SourceReadiness 返回 blocked：12 条规范管道缺失源、调度、配置和查询能力引用。该结果是实际产品入口的读取，未绕过 Web 检查身份的数据库角色拒绝。

另发现独立代码缺陷：services/aos-api/aos_api/routers/wave_ext.py::_pg_ot_row_count 捕获所有数据库异常并返回0，使数据健康和数据沿袭将权限/连接异常误当空数据。修复为稳定的 DATA_OBSERVATION_UNAVAILABLE / 503，不包含底层连接或凭据；正常0行和非0行不变。保留原 TenantScope，不补权限，不切换凭据。新增 services/aos-api/tests/test_data_health_observation_failure.py 先红再绿验证真实零值、正常数量、权限与连接失败；原当前数据真实性相关读接口回归。当前现场blocked不能由此修复宣称ready。
