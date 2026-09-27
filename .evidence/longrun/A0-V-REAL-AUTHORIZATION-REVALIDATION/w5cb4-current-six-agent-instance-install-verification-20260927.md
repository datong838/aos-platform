# W5CB4 当前六 AgentInstance 受控准备 verification（2026-09-27）

## 第 1–6 步：方案、受控实现、唯一执行、独立回读

- 编码前方案 `w5cb4-current-six-agent-instance-install-plan-20260927.md`，上位 231 A0-V/BG-00 和栖月汇 9.3/231-9；承接 `52ed9681` 当前定义来源回执修正。强一致记忆 `AOS-000802` CURRENT、validate GREEN；m1 单写者，原有脏测试与两个 test-only 文件未触碰。
- 代码 `scripts/a0v_current_six_agent_install.py` 默认只读，显式当前目标库连接和 `org-org/dev-project` 租户 scope；`--execute` 前 O_EXCL/fsync 唯一 intent，写前重做 preview 前置、六模板 hash/实例空状态，调用正式 `AipEcommerceAgentInstaller.install()` 一次。任何未知/部分状态不重发。
- 执行前只读：签名包当前定义 6/37/10、本租户 AgentInstance=0、SkillBinding=0、CapabilityBinding=0、Runtime binding=0，intentExists=false；`twa_org/twa_workspace` 各唯一存在。无效 intent 命令返回 `EXACT_INTENT_UUID_REQUIRED`，随后仍零行/无 intent。固定 UUID `df11df0e-feae-4c67-869f-be4714a23c61`，未换键。
- **仅执行一次**正式命令，返回 `CURRENT_SIX_AGENT_INSTALLED_EXACT`：6 个 created、回执 SolutionPack 1.11.0、本租户六实例、Skill/Capability/Runtime binding 均 0。intent 文件与目标 DB、租户、版本/ID 一致且持久保留。
- 独立 `BEGIN READ ONLY` SQL 列出六个 `ecommerce.*.default`，均 `provisioning`、模板 revision 1、source 1.11.0；`dev-org/dev-project` canary AgentInstance=0，本租户 SkillBinding=0、CapabilityBinding=0、Runtime binding=0。未调用激活/能力/业务命令。

## 第 7–8 步：测试、浏览器、安全及复审

- 常规专项+相邻累计 `34 passed, 1 skipped`；skipped append-only 当前定义/实例测试另在独立可清理 PG 会话 `1 passed`，包含当前定义 53 行逐 Owner 回读和六个 provisioning 实例安装回执。`git diff --check` 通过。
- 安全预览 8080 停旧进程后按 `a0v_current_preview_http.py --serve` 重启，启动回执 Runtime Host=0、workers=0、migration disabled；8080 `/openapi.json` 200，18181 无监听。浏览器 `/aip/model-runtime` 继续 0/6 可自动执行、已绑定 0、已启用 0，工作台无可见入口；这是正确禁入。安装仍 `not_prepared`，八项配置缺。
- 方案/代码一致：只准备六个 AgentInstance 身份，不建第二身份表、不绑 Skill/Capability、不放开预算/出站/模型、无 Provider/商城源/旧 Run/业务数据删除。六实例的存在不等于数字同事已经健康或首链自然成功。

## 第 9 步：下一波

- 先按责任计划/SkillBinding/CapabilityBinding 正式 Owner 盘点 37 技能与 10 能力的受控绑定路径及前置审批/预算/健康来源，切最小可合法执行的首链角色与能力；其他配置按 BG-00 八项推进。无正式费用、地域、审批选择不得自行激活。保持 Runtime Host/worker 关闭；安装页登记 503 的独立受保护身份门留待真正业务登记阶段。
