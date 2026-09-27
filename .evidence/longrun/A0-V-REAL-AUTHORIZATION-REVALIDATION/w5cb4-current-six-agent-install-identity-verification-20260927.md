# W5CB4 当前六角色实例安装身份代码核验（2026-09-27）

## 结果

- 编码前 plan `w5cb4-current-six-agent-install-identity-plan-20260927.md`；231 A0-V/BG-00 与栖月汇技术合同要求复用 AgentInstance 且精确来源。当前 signed 1.11.0 定义已发布，但未创建实例或 Runtime binding。
- `AipEcommerceAgentInstaller.install()` 的回执版本现在从已选六模板的唯一 source revision 推导：当前 `1.11.0→1.11.0`，旧 `1.2.0→1.3.0`；混杂/未知 fail closed。修正前当前来源会错误报告旧 `1.3.0`。无其他实例创建/运行语义改动。
- 专项+相邻累计 `32 passed, 1 skipped`；skip 为必须独立隔离 PG 会话运行的 append-only 53 行测试，前波已单独 GREEN。`git diff --check` 通过。
- 当前新库只读 `org-org/dev-project` AgentInstance=0、SkillBinding=0、CapabilityBinding=0；浏览器 0/6 可自动执行、安装 `not_prepared`。本子波未调用 `install-ecommerce`、未创建任何实例，Runtime/worker/Provider 仍关。
- 安装页登记 503 已定位为安全预览没有 `AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE`，`configured_registration_connection()` 返回 None；这是独立受保护登录门，不能用普通 Web/Runtime 登录代替，不阻塞本波无外部副作用代码修正。

## 下一波

- 先做唯一 intent 和当前租户六实例创建的文件级方案/隔离测试；若当前库六实例全零，单次正式 `install()` 后逐项回读 provisioning 状态、source 1.11.0、回执版本与本租户隔离。未知结果只读冻结，不换键重发；六实例仅身份准备，不表示 37 Skill 和 10 Capability 已绑定或可运行。
