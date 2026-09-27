# W5CB4 E08：SourceSelection 原命令只读回执计划（2026-09-28）

## 上位方案、现状与 Rules

依 231/231-9 的 BG-00→BG-01/02 首链与“未知结果不重发”军规，E07 已保证数据源登记有持久 Receipt；当前命名卷 `a0v_108` 仍是源 0、管道 0、运行绑定 0。现有 `POST /v1/pipelines/{pipeline_id}/source-selection-approvals` 将批准修订与幂等键同事务存入 `pipeline_source_selection_revision`，但没有按原键的只读产品对账口。发生响应丢失后不能把再次 POST、同源 GET 或 UI 状态当作原命令成功证明。本波补此正式只读口，为后续可恢复产品入口铺路，不创建源、管道、绑定或自然执行。

遵守：m1 单写不 push；先方案后最小代码；不读取商城源数据；不触发旧 12 Run/手工 `run_definition`；不删除卷/数据；只读缺失返回缺失而非授权重发。E08 不把代码测试当首链完成。

## 文件级清单与修改前 SHA-256

- `services/aos-api/aos_api/pipeline_source_selection_owner.py`：`94ce283d1904901cf20a2115194d2e1d149d07c0c3366c8ffd46b7cbc591b05a`。新增原 actor、租户、安装、generation、pipeline、key 精确匹配的只读回执读取；校验运行角色与保存行完整性，只回 `PipelineExactRef`。不以此授予当前执行权。
- `services/aos-api/aos_api/pipeline_control_service.py`：`1f5fb66b152ba9fc9b52db3468cdf5105e615820109d0102bf9700253aa9f522`。复用现有 tenant-scoped runtime connection，增加只读服务方法，不调用 append/当前源读取。
- `services/aos-api/aos_api/routers/pipeline_controls.py`：`ccb93cfea33d4725021f1973ac72525fd3fa8a3609c1c0098bbb9ec7129ce6fb`。新增 GET 精确查询，沿用 principal、工厂和安全错误投影；请求必须是规范 UUID 与原 `Idempotency-Key`。
- `services/aos-api/tests/extension_runtime/test_pipeline_source_selection_owner_pg.py`：`53ee8e198b30bb60fa54244de08623836ec16e4324f644f297b13cfaba3e6242`；`services/aos-api/tests/test_pipeline_control_http.py`：`9837d914ca980085032089485d2f1aeb72ebfa56598aed0dc1f9ef3e09bdc779`；`services/aos-api/tests/test_pipeline_control_service.py`：`77a3c145dbee14c75694721c8592753097cbd03610c9282b682a66809a2d127f`。覆盖原键命中、错租户/actor/安装/代次/pipeline/key 缺失、GET 不写且不重发、服务边界复用相同 scoped 身份/fence；HTTP 不泄露内部细节。
- `services/aos-api/tests/test_domain_router_manifest.py`：`82318ec6b239119d1bd16fbd50d31d7fbdc3b96dc1fcb72b71b152e96b6b9ee2`。仅因新增路径更新精确数量/摘要，保持重复路由 0。

## 串行验收与停止条件

1. 后端模型/HTTP/隔离 PG 专项与邻接回归；确认只读查询不访问源表、不生成执行权、不绕过 RLS。
2. 当前 `a0v_108` 命名卷只核对空态与认证/身份门；预览 profile 未提供独立 runtime worker 凭证时，正式回执 GET 应安全拒绝为 503，不能为得到 404 降权到 Web/超管连接。不提交真实 SourceSelection、不改变 approved 安装，不为了验收制造数据。
3. 最新代码自检：服务/页面版本与当前卷读回，浏览器确认空态和回执缺失安全文案；无凭证或 mall 读写。
4. 方案/代码一致性复审、verification 落盘、精确 commit、项目与 Prime 记忆更新。下一波 E09 复查正式管道/安装准备产品入口和当前源授权，优先打通可配置首链，不为补旧快照每一行耗时。

若发现既有回执行与键不唯一、数据库身份不明确或 GET 结果未知：停止本波写操作，冻结该键，仅做只读定位，不手工重发批准。
