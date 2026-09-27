# W5CB4 当前 signed AIP 定义发布 adapter 子波核验（2026-09-27）

## 已完成 / 第 1–7 步

- 上位复习：231 主序 A0-V/A1、栖月汇产品方案 9.3、当前强一致记忆 AOS-000802。`memory-status` GREEN_WITH_WARNINGS（七项强一致 CURRENT，eventual Codex note PENDING_ASYNC），`memory-validate` GREEN；本波不据 eventual 投影改业务状态。
- 文件级方案先于编码，见 `w5cb4-current-signed-aip-definition-execution-plan-20260927.md`；保护旧 `w5cb4-current-signed-aip-definition-publication-plan-20260927.md` 原文。
- `aip_solution_pack_publisher.py`：旧 `publish(1.3.0/source 1.2.0)` 不变；新显式 `publish_current_verified` 拒无 proof、校当前候选 6/37/10、将 source revision 明确为 1.11.0。它是内部 adapter，不是对任意目录的签名授权；当前 DB 写脚本仍须在同一执行边界 exact 重核。
- `aip_ecommerce_agent_installer.py`：当前 1.11.0 三类全量时选择它；当前全零兼容旧来源；当前任一部分行 fail closed，不从旧来源拼齐。
- 纯测试 23/23 通过：当前候选、两次核签前置、旧发布器、当前来源 payload、当前/旧来源单选及部分来源拒绝。`git diff --check` 通过。累计 API 用例另有 2 个 setup ERROR：共享夹具指向已不存在的 2026-09-13 旧签名目录，未进入测试体；不修旧卷、不将其报为功能通过。
- 当前库只读回读仍 `agent=0,skill=0,capability=0,runtime_binding=0`；8080 `/openapi.json` 200（一次 5 秒超时后 20 秒读回成功），8434 `/aip/model-runtime` 200。改动尚未加载进当前 API，浏览器当前投影应继续禁入；本子波不声称上线验收。

## 方案/代码复审、风险与第 8–9 步

- 与方案一致：仅来源适配与完整单选；没有发布 DB、Runtime Host/worker、Provider、商城源、旧 Run 或删除。用户预期的正式 6/37/10 发布、写前 exact、部分提交冻结、独立回读和浏览器六角色投影，**都尚未完成**。
- 下一子波先做当前专用受控写脚本/唯一 intent 与 read-only reconcile、隔离 PG 测试、修当前环境夹具输入；满足这些门后才考虑当前库单次写。未知提交或非全零现状即冻结，不重发。随后才是 BG-00 八类真实配置/绑定。
