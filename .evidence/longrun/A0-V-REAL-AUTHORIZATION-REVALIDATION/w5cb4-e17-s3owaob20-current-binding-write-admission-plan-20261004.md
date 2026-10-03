# E17-s3o-w-ao-b20｜当前预览 Capability Binding 私有身份写准入文件级方案

## 上位方案与已读事实

- 231-4、AIP-7 22、BIND-1 31 要求非 owner 最小角色、租户 RLS、独立 issuer/Reader、外部身份；b17-b19 表明当前 DB 只有 owner 可连，正式 Reader/Capability issuer role0、`.env` 有效 `AOS_AIP_BINDING_*`/OIDC key0，runtime对共享 Receipt INSERT=true且 operation guard 未完成。
- `services/aos-api/aos_api/routers/aip_bindings.py:build_capability_binding_service()` 在两组私有配置全空时退回 `AipCapabilityBindingService()`，它默认使用普通 DB连接；当前签名预览由 `scripts/a0v_current_preview_http.py` 运行，但 FLAGS 尚未要求私有 Binding 写身份。不能因前端 blocker 就假设 HTTP Capability 命令没有 owner 写路径。
- 既有 UI/configuration stage 身份部署脚本按 clone→私有凭据→精确 DB CONNECT→主库回读，并依当时独立 lease/迁移版本。不能把它们的旧角色/凭据/lease 直接套到当前 E17；当前真实库仍只读，正式 OIDC/Owner缺失。

## 文件级最小改动与 RED

1. 只新增当前签名预览模式专用环境门 `AOS_AIP_BINDING_REQUIRE_PRIVATE=1`（`scripts/a0v_current_preview_http.py:FLAGS`）。`routers/aip_bindings.py` 在该门打开且 Reader/issuer 两组私有配置没有全部精确齐备时，对 Capability Binding **写**命令（create/evaluate/activate/suspend/revoke）于服务调用前报稳定503；列表/详情继续调用原只读路径。现有普通开发模式和 Skill Binding 不改；所有有限配置校验沿用原 `build_capability_binding_service`，不能把仅有 env key 冒充成功连接/授权。
2. 先写目标失败测试，验证门开且无正式双身份时，5类命令均不调用服务/不产生 DB副作用；读列表/详情继续走真实服务。门关保留既有行为；双身份配置不完整/同凭据仍由原工厂失败。测试中的 spy 仅证明拒绝发生在任何 Store调用之前，不作为业务首链验收。
3. 最小改原路由、预览 FLAGS；跑专项和相邻回归、静态检查。若改运行代码，按最新 m1/原卷135与签名来源，PG→API→Web 完整重启；API 端点用真实当前身份只读对账，浏览器 `/aip/skill-publish` 再核3 blocker/禁用/无业务入口，Host/worker/Provider关。不得以 503 代表正式链完成。
4. 方案/代码复审、verification、m1 精确提交，AOS/Prime/D-waves 同步。真实主库 DDL/正式 Reader/issuer DB CONNECT、外部 OIDC、operation scoped Receipt仍为后续独立门；`org-org/dev-project` 唯一正向，`dev-org` 零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
