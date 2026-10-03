# E17-s3o-w-ao-b16｜正式身份来源与恢复库 ACL 差异负门

## 只读实测

| 门 | 命令/输出/退出码 |
| --- | --- |
| 当前原库身份/共享 Receipt ACL | `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -U aos_app -d aos_current_preview_20260927 -X -A -t -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY; SELECT current_database(),(SELECT version_num FROM alembic_version),(SELECT count(*) FROM pg_roles WHERE rolname IN ('aos_aip_binding_readiness_reader','aos_aip_capability_issuer')),has_table_privilege('aos_runtime','public.aip_agent_registry_receipt','INSERT'); COMMIT;"` → `aos_current_preview_20260927|a0v_135|0|t`，exit0。 |
| b15 恢复库同一只读查询 | test-only context/container，库 `aos_e17_s3owaob15_restore_20261004` → `aos_e17_s3owaob15_restore_20261004|a0v_135|0|f`，exit0。数据 26/26 一致，但 b15 `pg_restore --no-acl` 使权限形状不同。不能把此克隆的 issuer 通过或 Reader apply 直接外推成原库可切换。 |
| 本机有效配置来源 | 只解析 `.env` 的非注释 key 名，不读 value：`AOS_OIDC_*` 0、`AOS_AIP_BINDING_*` 0，exit0。现有 `aos-recovery/.aos-testonly-bg00cf-3r_lw6yp/api-service-identity.json` 名称为 testonly、0600；不得给当前 API 复用。 |
| 原代码门 | `aip_bindings.py:build_capability_binding_service` 要求同库不同私有 Reader/issuer passfile；`a0v_current_preview_http.py:_require_external_oidc` 要求 HTTPS issuer/JWKS/audience；`aip_registry_issuer_connection.py:_require_identity` 要求 runtime 不能对共享 Receipt INSERT。三者与当前缺口吻合。 |

## 复审/结论

- 当前原库 runtime 对共享 Receipt INSERT=true，且仍有其他合法 operation；全表撤权会伤正常功能。b8/b12 的 test-only Tool 探针未冻结正式 operation scoped 发行协议。原库 role0、正式 OIDC/Binding 配置0，当前库切换和 Host/自然首链继续失败封闭。
- b15 仅证明**数据**可恢复，未证明全量 ACL/roles 恢复；恢复库 26表摘要一致不能替代权限同形状。下一波必须先设计并复演包含 globals/ACL 的隔离恢复或精确权限增量，再以实际原库权限形状做发行身份 RED；缺正式来源时继续独立配置/绑定开发。
- 本波没有代码、迁移、API/Web/UI、原库或克隆写入；专项为上述两个 `BEGIN READ ONLY` 和 key 名核验，均 exit0。浏览器不适用于只读 ACL 负门；此前 b10 当前代码/页面验收仍适用，无本波重启。`org-org/dev-project` 唯一正向，`dev-org` 零副作用；Host/worker/Provider关，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
