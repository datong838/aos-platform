# W5CB4 BG00ci｜当前正式身份与 checker 来源只读对账

## 基线与方法

依据 BG00ci 文件级方案、231-4/231-5 与 BG00ch 正式外部 OIDC 门；m1 基线 `d7cdbe50`，Authority `AOS-000937`。仅对当前命名卷 `aos-a0v-recovery-pg-data` 上 `aos_current_preview_20260927` 执行 SELECT；只输出组织、角色及行数，不输出 subject、token、Secret 或商城源数据。`dev-org` 只作为零写 canary 过滤条件。

## 本次可复核输出

| 检查 | 命令/来源 | 退出码与输出 |
| --- | --- | --- |
| 当前库与迁移 | 容器内 `psql -At` 查询 `current_database(), alembic_version` | 0；`aos_current_preview_20260927|a0v_117` |
| 当前工作区与成员 | `twa_workspace`、`twa_ws_member` 按两个精确 tenant 聚合 | 0；仅 `org-org|dev-project|1` 与 `org-org|dev-project|owner|1`；dev-org 无行 |
| 实际 Action 成员/授权 | `meta_membership`、`authz_tuple` 按精确 tenant/role/relation 聚合 | 0；仅 `membership|org-org|dev-project|owner|1`；无授权 tuple 聚合行 |
| 网络审批链 | `aip_action_proposal`、`aip_action_approval_event`、`aip_network_policy_receipt` 按两个 tenant 聚合 | 0；三表均无匹配行 |
| 当前安装与制品 | `bundle_installation`、当前 `bundle_installation_revision`、`asset_bundle_version` 聚合 | 0；栖月汇安装 1、active revision 0、当前 revision `approved` 1；`published` 4、signature 非空 4 |
| 当前签名预检 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` | 0；`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、库 `a0v_117`、安装 approved、published 4、runtimeBindings 0；检验当前签名根与 Receipt，不据此宣称可运行 |
| 当前 OIDC 配置入口 | 只读取 `.env`、`apps/web/.env` 的变量名，`launchctl print gui/<uid>/com.aos.a0v-api-daily0900` 只提取键名 | 0；均无 `AOS_OIDC_*` 或 `AOS_AUTH_*` 键；API 8080 与 Web 8434 正在监听 |

`ecommerce_event_proposal_gate.require_internal_event_binding` 要求当前 `meta_membership` 的精确 actor 和角色；网络 Approval consumer 要求批准 event 来自非 maker 的 `checker.1`，重新核 checker 当前角色与绑定哈希。当前唯一成员不能构成独立 maker/checker；没有现行外部 JWKS/issuer/audience，BG00ch 的受限 API 会以 `EXTERNAL_OIDC_CONFIG_REQUIRED` 禁入。以上是对已知启动配置入口的核查，不能证明外部 IdP 不存在，只能证明当前实例没有可用正式接线。

## 结论与下一波

当前实例不具备正式 OIDC + 第二独立 checker + 已批准安装的 active binding，Host/worker/Provider 保持关闭，18181 不监听；不以 owner、开发 JWT、克隆正例或签名预检代替正式业务链。当前库未写、未切换 API 身份、未回放 Run。

BG00cj 在独立克隆/代码层处理网络 ApprovalEvent 的专用签发者与数据库不可伪造边界；先细化方案、RED，再最小实现和回归。真实 IdP/第二 checker 的当前实例接线留在 E17，缺正式 authority 的实例继续禁入。当前 API 的 `aos_app` owner 切换另需备份、克隆全链和零执行窗口。浏览器工具本波不可用，未声称页面交互或截图验收。
