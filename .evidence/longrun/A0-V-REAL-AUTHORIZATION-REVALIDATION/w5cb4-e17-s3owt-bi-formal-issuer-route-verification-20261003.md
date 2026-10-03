# s3o-w-t 第一切片｜BI HTTP 共享身份写入口禁入

- 基线 `m1@8cd2be15`、Authority `AOS-001232`、代码/当前库 `a0v_135`。依据 231-3、231-9、D-wave s3o-w-t 和本波文件级方案。当前真实库只读。
- 只读实测：原权威库登录 `session_user=current_user=aos_app`；`aos_bi_plan_issuer` 角色0、四个 test-only 函数0、当前 Plan/BI Receipt0；API/Web LaunchAgent 未配置外部 OIDC 字段或发行凭据文件。原 HTTP `get_signed_bi_preparation_service` / `get_signed_bi_rebind_service` 默认返回模块级服务，底层 `db.connect(scope)` 使用共享 API 连接且会 `SET LOCAL ROLE aos_runtime`；它无法代表隔离发行身份。
- RED：新增默认写依赖不得返回共享服务的专项测试，实际 `DID NOT RAISE ApiError`，exit1。GREEN：默认两个 BI 写依赖返回 `BI_FORMAL_ISSUER_REQUIRED` 503；只读 admission/Receipt 依赖和其它合同路由未改，注入专用服务的路由参数/强 ETag 合同保持。
- 验证：专项 `1 passed`、相邻 BI/安装/当前权限 `98 passed`、原签名 Growth1.13 全 schema 克隆 `1 passed`，均 exit0；`py_compile`、`git diff --check` exit0。一次性测试库/发行角色/函数无残留。克隆仍能作为原 Store/SQL 的隔离证明，不能算当前 HTTP 正向。
- 风险与下一步：默认 HTTP 写入口现明确禁入。正式替换须独立 OS UID 的受保护凭据与私有 IPC、外部 OIDC JWT 每请求重验、精确 actor/租户/安装 ETag/幂等，以及四函数/ACL 的 full-schema 克隆恢复演练；不可将同 UID API 的连接字符串或可自设 GUC 当成发行身份。正式 migration/当前库切换须新一致备份、全链克隆、零执行窗口。Host/worker/Provider继续关闭，首链 pending。
