# W5c7o 同一 `_load` Claim 复用等价性负例方案（2026-09-25）

## 上位与现状

231/231-5 的自然运行、当前权限、原代次/截面和失败恢复不可弱化。W5c7n 长例正式 GREEN 且子段定位 claim 读回耗时；W5c7l 仅许可研究同事务、同一 `_load` 内复用，未证明安全。`PipelineSourceClaimOwner.read_current` 每次执行 loop 身份/同连接同事务校验、当前控制/安装/运行守卫、Run 锁与 claim 读；`GroupClaimOwner` 先读全部成员，随后 `_bound_parent` 再通过 `ControlledIngressJournal` 重验。claim 表虽有 RLS 与 immutable 触发器，也不能据此跳过外部 current 控制读。

## 文件级九步

1. 复习上位 231/231-5、W5c7l/m/n、SourceClaim/GroupClaim/InputOwner/ClaimLoop、a0v_024 RLS+immutable、现有 InputOwner PG 负例。
2. 本方案先提交；新增仅测试文件 `services/aos-api/tests/extension_runtime/test_a0v_w5c7o_same_load_claim_equivalence_pg.py` 和审计/verification 证据。不改生产 `aos_api/`、DB、索引、部署。
3. 在隔离 PG 原始 2-member fixture 中计数/标记 current claim 读回边界，证实 callback 前/后 `_load` 与 `_bound_parent` 顺序；模拟第一次 group claim 已通过但 parent 独立重验拒绝，必须在 consumer 前 fail closed；模拟 callback 后 current deny，必须拒绝最终完成。
4. 覆盖 completed/recovery 的差异：原始 completed 只读与 saved recovery 不得借 running 结果复用；若 fixture 无法覆盖，记录为未证并作为下一波硬前提，不能声明同一 `_load` 优化等价。
5. 运行专项、InputOwner/ClaimOwner 相关 PG 回归与既有累计短回归；用后停隔离 PG。长例 W5c7n 已 GREEN，本波不重复。
6. 浏览器只读 rev4 disabled，不保存/运行/冲刷队列。
7. 复审是否存在可证明等价的最小切片；若任一锁序/并发/完成态/恢复态/错误码未证，结论保持“不授权生产优化”。
8. verification 提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c7p：针对 W5c7o 遗留的精确未证合同，方案先行做独立 PG 对抗测试或只读 DB 证据，不触真实 closure。

真实 A0-V closure 仍无授权；旧 attempt 不重发、不手工 `run_definition`；商城源行不读，230 L0 挂起，dev-org 零 canary，m1 单写不 push。
