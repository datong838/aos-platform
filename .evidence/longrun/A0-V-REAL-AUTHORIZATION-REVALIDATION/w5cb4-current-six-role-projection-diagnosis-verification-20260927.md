# W5CB4 当前六角色投影差异诊断 verification（2026-09-27）

## 只读事实

- 浏览器 `/aip/model-runtime` 的跨页投影报 `ecommerce agent definitions differ from 6-role authority`；同页模型路由/供应商均 0，未提供可执行链。`AipOperationalProjectionStrip` 读 `/v1/aip/operational-projection`，后端调用 `AipEcommerceAgentInstaller.runtime_readiness()`，其 `_definitions()` 要求当前来源的 6 AgentTemplate、37 SkillTemplate、10 CapabilityRevision，缺 6 Agent 即抛上述错误。
- 在当前新库 `aos_current_preview_20260927` 上只读 COUNT：`aip_agent_template_revision=0`、`aip_skill_template_revision=0`、`aip_capability_revision=0`、`extension_runtime_binding=0`。这说明该错误是正式定义完全缺位，不是一个已安装数字同事的健康状态被错误翻译。
- 当前库 Registry 精确 JOIN 回读 `solution.ecommerce.growth|1.11.0|published`。现存 `AipSolutionPackPublisher` 的 `SOLUTION_PACK_VERSION=1.3.0`、`AIP_DEFINITION_SOURCE_VERSION=1.2.0`；源码目录 `bundles/solutions/ecommerce-growth/bundle.yaml` 也为 `1.3.0`。因此现有 AIP 发布器不能直接代表当前已签名 `1.11.0` 包发布定义，更不能靠手工 SQL 补 6/37/10。

## 裁决

- 保持投影错误、工作台禁入和 Runtime binding 0；本波无代码修改、无数据库写入、无旧卷/商城源读取。测试为读回与代码追踪，不能写作六角色已就绪。
- 下一波先查当前 `1.11.0` 签名包是否包含可由正式 Owner 解析的六角色/37 逻辑/10 Capability 定义；若可，按当前包内容更新发布器契约并做隔离测试、正式发布/精确回读；若不可，先补构建/包合同，不以旧 `1.3.0` 内容冒充当前包。需保留发布副作用、幂等、租户与预览禁入边界，后续单独方案再编码。
