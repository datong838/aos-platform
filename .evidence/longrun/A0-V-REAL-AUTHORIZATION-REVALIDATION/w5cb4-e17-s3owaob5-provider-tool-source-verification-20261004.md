# E17-s3o-w-ao-b5｜当前 Provider/Tool 正式来源只读核验

## 读前合同

按同前缀 plan 复习 231、AIP-7 22、BIND-1 31；Provider 必须精确插件批准、`secretRef+version`、健康/Eval/预算/容量，ToolBinding 必须有正式签名 ToolDefinition、独立 issuer 和同事务 Receipt。当前原库只读；未读商城业务源或凭据。

| 核对 | 精确证据 |
| --- | --- |
| 签名安装 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` exit0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，`a0v_135`、Installation approved、publishedVersions4、runtimeBindings0、当前 signedRoot/trustRoots 精确回读。首次误用系统 Python3.9 导致 `datetime.UTC` ImportError exit1，换服务 venv Python3.11 后通过；这不是安装失败。 |
| 当前四签名制品 | 仅读上述 signedRoot 的四个 `bundle.yaml` 结构和文件名：core1.4、niushop1.23、growth1.11、operations-base1.2；四个 manifest 没有 `tool` 键路径，四树没有 Tool 命名文件。未读取 `platform.ecommerce.niushop` 的映射/商城源内容。既有 s3o-w-n 审计也记录无 durable ToolDefinition。仅按当前安装四份判定，不能声称其他未来制品不存在。 |
| 正租户当前数据 | `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -X -qAt -v ON_ERROR_STOP=1 -U aos_app -d aos_current_preview_20260927 -c 'BEGIN READ ONLY; ... COMMIT;'` exit0：`org-org/dev-project` Provider head0、Provider health0、RegisteredModel head0、ModelRoute head0、ToolBinding0、RegistryReceipt6；最后6条不能当作 ToolBinding 发行 Receipt。未读取 dev-org 数据。 |
| Provider 插件批准 | 仅元数据读取 `plugins/llm-providers/*/approval.json`：3个批准 sidecar（agnes-text/image/video）均为 `approved_for_dev`，owner `AOS/FDE`，允许正租户；`aip_provider_plugin_authority.py` 当前仅接纳该开发批准状态。`publish_provider` 需 exact pluginRef，但本次未发现当前正式外部 OIDC Owner、secretRef exact item、健康/容量来源；开发批准不能冒充正式运营许可。 |
| 原 Tool 写链 | `aip_assignee_resolution_store.py` 的 `upsert_tool_binding` 直接调用普通 `db.connect`、校验 active Agent 后写 `aip_tool_binding`，未在同事务写 `aip_agent_registry_receipt`；`test_e17_s3or_tool_binding_source_receipt_pg.py` 已以 strict xfail 保留缺口。HTTP 有 OIDC/角色门，但当前正式发行来源和专用非 owner issuer 仍缺。 |

## 决定

- Provider 当前实例缺正式插件批准协议、OIDC/Owner、secretRef、健康/容量与 exact Model/Route；不创建虚假 Provider，不启用 Provider。Tool 当前四签名制品缺 ToolDefinition，原 upsert 缺同事务 Receipt 与专用 issuer；不能把内存工具列表、普通 owner 或测试账号当来源。
- 下一步不等待两类外部来源：在可销毁隔离 PG 对原 ToolBinding active 写链做**精确禁入 RED**，证明无当前签名 ToolDefinition/发行 Receipt 的请求不能留下 active binding。先复审现有 strict xfail 与当前 API/Store 合同，文件级方案后最小修复；disabled 撤销旧 binding 保持。该安全切片只证明禁入，不宣称正式发行正向或首链。正式 ToolDefinition/issuer/Receipt 设计仍单列下一波。
- 本波只读、无生产代码/页面改动，浏览器不适用；原库只读、Host/worker/Provider关闭。目标状态仍首链 pending。
