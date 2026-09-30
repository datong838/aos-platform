# W5CB4 BG00do｜签名 BI 职责模板到配置 Plan 的启动合同审计

## 上位与现场

复习 231 主计划、231-2 签名 artifact/精确 lock、231-3 approved→准备/验证→配置→启用、231-9 数字同事实例与职责计划、栖月汇 BI 产品角色模板。BG00dm 在 test-only 克隆把 growth1.12 签名 release 发布并建立第二个 approved@3/active NULL 安装；当前真库仍旧 growth1.11/approved@3，不触当前写。1.12 signed tree 的 `content/responsibility-templates/business-investigation.readonly.json` 已有六个规范职责 slot，不含 assignee 或批准身份。

## 复核到的关键依赖环

`ecommerce_business_investigation_aip_authority.build_responsibility_plan_request` 仍填 `published_template_ref("ecommerce.business-investigation.readonly")` 产生的本地静态 ref；`resolve_responsibility_template` 对这个 ID 直接比较本地 hash 并返回 true，未读安装或签名 artifact。实际 `InstalledProductionProfileResolver` 只查 `installation.active_revision` 和 active 状态，克隆新安装 approved@3/active NULL 因而取不到。其 `_row_matches` 还要求 `bundle://aos/solution.ecommerce.growth@1.12.0/...` 规范前缀，而 BG00dm 新 Registry 持久 artifactRef 为签名源别名 `bundle://a0v-growth-112/solution.ecommerce.growth/1.12.0/...`，即使伪设 active 也不匹配。不能把“本地静态 true”当签名来源，也不能直接删除而使启动配置环永久无入口。

## 下一独立 BG00dp 文件级 RED/施工边界

1. 先在 `services/aos-api/tests/aip/test_aip_responsibility_template_authority.py` 与 `services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py` 写 RED：本地静态 ref 在生产拒绝；只有精确租户、唯一 approved/active 安装、签名 1.12 release、lock 成员、artifact digest/字节/模板 schema 一致时才可作为**配置准备**模板来源；错租户、旧1.11、多个安装同 ref、撤签/到期、原 lock 漂移、别名不受信、篡改字节、未安装均拒绝；返回可追溯 exact ref/安装引用，不产生 active/binding/业务端口。
2. 最小修改 `aip_responsibility_template_authority.py` 的专用准备态解析器以及 `ecommerce_business_investigation_aip_authority.py` 的 Plan request 来源；复用既有 ReleasePolicy、签名根和只读 tenant connection，不能仅放宽 `_row_matches` 的 URI 或 status 条件。必要时只加窄只读 Store/DTO，明确 approved 读取不等于运行许可；不改通用媒体模板和既有 active 路径。
3. 用 BG00dm test-only 克隆验证 signed template 的拒绝/可用边界；当前库保持只读，正式 key/checker/三身份仍需独立 authority。Plan 的 assignee、档位治理、审批与八候选其余七类各走原严格门；不自动创建 Plan。方案/代码复审、专项/累计、verification、上下文后再进入下一波。

本波是只读合同发现，BG00dp 才改生产代码。禁止用 test-only 双根或角色字符串冒充当前正式身份，不启 Host/worker/Provider、不读商城源、不重放旧12 Run、不手工 run_definition、不碰230 L0、不 push。
