# W5c5g 真实关闭门只读组合判定方案（2026-09-25）

上位 231 A0-V/231-9 BG-00。W5c5b 的严格时钟/原组门、W5c5c 的本机已知 Host 进程门、W5c5d 的正式受管 connector、W5c5e 的独立未关闭审计、W5c5f 的受管 Host 目录门分别 GREEN/WAIT，却不能相互替代。本波把这些结果组合为**明确缺口列表**，而不是提供关闭执行器；默认 `closureAuthorized=false`。

## 文件级九步

1. 复习各门 verification、`a0v_091` 原子关闭/Receipt 合同和当前严格 24h 时点。
2. 文件仅本方案、新增 `scripts/a0v_w5c5g_real_closure_gate_composition.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5c5g_real_closure_gate_composition.py`、本 verification。正式 Owner/Host/DB 迁移不改。
3. 只读调用已有门，显式区分 `WAIT_24H`、`UNKNOWN/FROZEN`、`INCOMPLETE_TOPOLOGY`；绝不生成 idempotency key/intent、调用 close 或读商城源行。即使时间门到线，受管目录与本机进程也不能证明全机第二 Host=0，故返回需单独真实方案和权威门的缺口。
4. 专项覆盖等待、到线但拓扑不完整、任一门冻结、Receipt 已关闭/状态漂移；任何未知冻结，不自动重试动作。
5. 有界累计 W5c3–W5c5g 与相邻合同，隔离测试库若启则停。
6. 浏览器只读核整组配置；页面不证明任一 DB 门。
7. 一致性复审：组合门是诊断，不是事务锁、全机视图或执行授权；未来到线后仍需独立真实关闭 plan→唯一 key→正式 Owner 一次→独立审计→退休/direct successor。
8. verification 提交后 CAS 同步 docs/AOS 项目开发上下文及 Prime 独立受管记忆、读回。
9. 下一波 W5c5h：优先完成可验证的全机拓扑权威来源或其他安全债；不可凭此组合器执行真实关闭。

m1 单写不 push；旧 attempt 不补跑；230 L0 挂起；dev-org 零 canary；未知冻结。
