# W5 前置：8080 受管重启与修复加载核验（2026-09-24）

## 方案与边界

- 依据 `docs/palantier/20_tech/电商平台接入/微商城电商接入方案/D-waves/2026-09-24-无人值守交接简报-双绿后执行序列.md` 的“待激活修复”和重启后复扫清单。
- 用户明确授权重启 8080；本波不改 plist、不迁移数据库、不读取商城源数据、不启动第二 Runtime Host、不手工 dispatch。
- 只验证服务重新加载和安全的路由/校验样本；完整受权复扫仍是后续独立门禁。

## 执行与结果

- `m1` 基线 `1a21e341`，重启前工作树干净；旧 uvicorn PID 36582 启动于 2026-09-23 20:47:17 CST。
- 2026-09-24 09:55 CST 通过 `launchctl kickstart -k gui/501/com.aos.a0v-api-8080` 受管重启；新 PID 92534 启动于 09:55:59 CST，`/v1/health` 返回 200，启动日志为 `Application startup complete`，未见启动错误。
- `GET /v1/exportable-markings/can-export?connection_id=c&markings=public` 仅记录状态码：200；旧进程取证为 404，证明此路由修复已被新进程加载。
- 匿名 `GET /v1/logic-flows/executions` 和 `GET /v1/aip/capacity/usage?limit=-1` 均为 401；不能据此判断业务行为。首次容量探针误用 `/v1/capacity/usage` 得 404，已纠正路径，误探针不计入验收。
- `GET /v1/functions-runtime/functions/nonexistent-ts-signature-probe/ts-signature` 返回 404；仅作缺失路径的状态观察，不以单点替代 NOT_FOUND 族级复扫。
- 定向回归：`test_router_route_precedence.py`、`test_route_param_bound_family.py`、`test_not_found_status_mapping.py`、`test_media_set_browser_interaction_router.py`、`test_get_route_body_family.py`、`tenant_isolation/test_ti0c_auth_effective_coverage.py`，98 passed、7 warnings，160.23s。

## 未完成与下一波

- 8 族修复已加载的证据不等于 8 族全量线上验收；交接清单中的五批受权复扫尚未执行。匿名 401 是当前鉴权边界，不使用开发万能令牌绕过。
- 当前 W4 `w4-stalled-group-closure/` 尚无结果文件；W5 只读 verify 显示旧 definition rev3 disabled、新 definition 不存在。W3 的 GREEN 是另一批历史组，不能替代 W4。
- 下一波：W4 到达 2026-09-24T02:39:44.133380Z 法定 24 小时门后，先 `prepare`，精确核对 12 stalled、definition disabled、receipt 0、canary 0；只在判据全满足时串行 `apply`、`audit`，每段独立冻结与回读。任一未知提交边界停止重发。
