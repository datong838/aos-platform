# W5CB4 当前六 AgentInstance 受控准备计划（2026-09-27，编码前）

## 目标/不做

- 当前 signed 1.11.0 的 6/37/10 定义已独立核实，`52ed9681` 修复实例安装回执版本。按 231 BG-00、栖月汇 9.3 与 231-9 合同复用公共 AIP AgentInstance；仅在 `org-org/dev-project` 建六个 `provisioning` 身份，不启用、不绑定 Skill/Capability/Runtime，不触发模型/业务/外部动作。
- `dev-org/dev-project` 仅零 canary；不读商城源，不触碰原 12 Run/旧卷/其他分支。当前安装 `not_prepared`、八项 Runtime 配置缺，不能因六实例创建称可运行。

## 文件级顺序

1. 新增 `scripts/a0v_current_six_agent_install.py`：默认只读；复用 signed Receipt 当前安全 DB/四包/唯一安装前置，并用显式 `connect_factory` 读当前 6/37/10 及本租户六实例现状。仅精确零实例、Runtime binding=0 可进入执行。
2. 显式 `--execute --intent-id df11df0e-feae-4c67-869f-be4714a23c61` 前 durable `O_EXCL` intent 到签名 Receipt 同级，fsync 后再次读回来源/DB/实例零；任何已存在 intent、部分实例或未知边界冻结，不重发。只调用正式 `AipEcommerceAgentInstaller.install()` 一次，固定 `org-org/dev-project` 和独立 actor；任何异常不隐式重试。
3. 写后逐个正式 Owner readback：六实例 ID、tenant、template revision/hash/source 1.11.0、状态 `provisioning`、Receipt；返回 `solution_pack_version=1.11.0`，并核 SkillBinding=0、CapabilityBinding=0、Runtime binding=0。
4. `services/aos-api/tests/aip/` 当前专用纯/隔离 PG 故障测试，覆盖 intent 重复、当前来源缺失、零/部分/全量、tenant drift、old source 混入、写后不符；专项与累计。当前库实际写前再独立只读核对。
5. 若 1–4 绿，再唯一 intent 单次实际执行、独立 SQL/浏览器回读；verification→m1 commit→下一波正式 Skill/CapabilityBinding/责任计划配置。未知/部分行停在正式恢复方案，不补发。
