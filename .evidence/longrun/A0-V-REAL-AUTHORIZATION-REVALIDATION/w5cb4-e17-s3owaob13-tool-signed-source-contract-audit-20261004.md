# E17-s3o-w-ao-b13｜当前 Tool 签名来源与公共发行合同审计

## 文件级方案与读前边界

- 按 231 安装/签名、BIND-1 31、W-L20 128 与 D-wave b13，限定读签名 receipt、四份 `bundle.yaml` 的**结构键与文件名**、原 `UpsertToolBindingRequest`/Store、W-D3 92/W-T2 102；不读取商城映射或源数据。只在能核验 exact ToolDefinition、安装 epoch、Owner/撤销及专用 issuer 的情况下设计正式 active 写路；否则先记录缺口并转独立主线。
- 方案候选：签名制品需声明 canonical ToolDefinition 的 id/revision/hash、bundle digest、租户与安装 epoch，Receipt 同事务结果必须与该 exact 来源及当前 Agent/Capability 绑定。普通 runtime 不能发 Tool 专用 operation，但共享 Receipt 的其它合法生产者不得被一刀切撤权。本段是待评审合同草案，不是已批准的产品或迁移协议。

## 当前只读结果

- 服务 Python 的 `a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` exit0：原卷 `a0v_135`、安装 approved、四个 publishedVersions、runtimeBindings0。只枚举 signedRoot 四份 `bundle.yaml` 键路径与同树文件名：core1.4、niushop1.23、growth1.11、operations-base1.2 均无 Tool 键路径及 Tool 命名文件；未读取 niushop 映射内容。限定当前四制品，不声称未来制品不存在。
- `W-D3` 的 requiredToolRefs 是 EvidenceBundle 投影，`W-T2` 默认工具包中的 `cap.*`/`clarify.request` 是面板占位；两者都不是安装签名 ToolDefinition 或真实 Tool invoke 准入。`W-L20` 证明解析缺 exact binding 会禁入，未定义签名 ToolDefinition 发行。原 DTO 只有 toolId/version/AgentInstance/status/Capability/Policy，无 sourceRef/安装 epoch/Owner；原 Store 仍普通连接写、无同事务 RegistryReceipt，旧 strict xfail 未消失。
- b12 的双向 DB 事务隔离仅在一次性测试库有效，`xmin` 未经持久协议/并发/历史行审查，不可直接做生产迁移。当前正式来源/发行身份不足，故本波没有生产代码、迁移、API/UI 或当前库写入，不宣称 Tool 正向。

## 决定与下一安全入口

公共 ToolDefinition 签名/撤销语义及 Receipt 持久配对字段必须在产品和技术方案中明确后再改正式 DTO/Store/ACL；本波不擅自把面板占位升级为 Tool 权威。当前 Tool 实例局部失败封闭，转 D-wave 已登记的八配置合法生产者与当前 Reader/身份链，优先找不依赖缺失正式签名 Tool 的来源。原库只读、Host/worker/Provider关，Goal active、不 push；org-org/dev-project 唯一正向，dev-org 零副作用，不读商城源、不重放旧12 Run、不手工 Run、不碰230 L0。
