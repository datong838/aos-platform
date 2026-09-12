# 管道控制正式审批入口

2026-09-12，基线21b4e0ea，沿有效A0-V主任务m1 Lease（独立子Lease与主Lease重叠被拒绝，不重复登记）。本波承接生产工厂及已部署a0v_022/023；不修改数据模式、不启用P01。

新增 services/aos-api/aos_api/routers/pipeline_controls.py 和 tests/test_pipeline_control_http.py；在 routers/domain_manifest.json 登记并由 scripts/generate_domain_aggregates.py 生成 domain_aggregates.py。

两个POST /v1/pipelines/{pipeline_id}/source-selection-approvals 与 /runtime-control-approvals，仅接受draft和可选previousRef。actor=Principal.subject、scope=Principal租户；请求scope和路径必须相同，禁止客户端actor/数据库连接/权限布尔值。使用既有强类型草稿及exact前序引用；ISO时间用Pydantic严格JSON模式解析，其他数值不放宽。请求体解析失败统一422且不回显输入。前序ref类型和规范UUID需在调用服务前检验。Idempotency-Key必须恰好一个，沿既有校验。

按当前控制平面pipeline_control_factory构造现有服务，调用approve_selection/control；当前权限、幂等、前序CAS均留在Owner，不复制SQL。返回持久exact引用200（包含首次与重放），不返回enabled或executionGranted。Owner冲突/权限/缺失映射为稳定409/412/403/404；非法引用422；未配置及存储未知失败503，固定无敏感信息，不在HTTP适配层自动重发。客户端遇到未知结果只能以同一幂等键核对，不能换键另发。

验收：HTTP请求真实JSON时间成功；scope/path/actor/宽泛字段、重复或缺少幂等头、坏前序类型/UUID在服务调用前拒绝；Principal身份唯一；既有Owner错误映射稳定、异常含秘密不回显、缺工厂不降级。验证生成清单一致、相关合同/Owner/工厂回归与闭包。HTTP测试使用替身仅证明传输绑定，不冒充真实审批。真实API仍旧进程，待正式部署波次重新加载和验收。

下一波把当前运行控制接进唯一ScheduleRun/Ingress事务和原批次恢复；避免旧live开关直接触发无界读取。之后补页面候选/审批交互及真实P01执行，不能要求经营用户手抄这些exact引用。

复核补充：请求最大64KiB、同步Owner调用移入现有线程池避免阻塞事件循环。当前OpenAPI已登记两个路由及响应类型；请求使用严格原始JSON解析以接受ISO时间并防止校验错误回显敏感输入，请求体详细schema尚待页面接入时补齐。主任务Lease保持ACTIVE，不以完成一个HTTP子步骤结束整个A0-V任务。
