# W5c5e 真实 stalled 关闭独立只读审计器方案（2026-09-25）

上位 231 A0-V/231-9 BG-00；W5c4y/z、W5c5a 已证隔离 SQL 正反合同，W5c5b/c/d 只读门逐层补齐。真实组未到严格 24h，本波只制作**关闭后**独立审计器和待执行清单，不创建真实关闭 intent/key、不调用 Owner。

## 文件级九步

1. 复习原 W3/W4 正式 close/audit 脚本、`a0v_091` Receipt/Run 终态合同、W5c4t 原组效果计数与安全边界。
2. 文件清单：本方案；新增 `scripts/a0v_w5c5e_independent_closure_audit.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c5e_independent_closure_audit.py`；本 verification。Owner/迁移不改。
3. 只读脚本用精确目标 group 查询定义 rev4、原 claim、12 Run、唯一 stalled Receipt、Store/link/projection/canary 总量、七类效果计数和唯一失败 attempt；不读取商城源行。Receipt 存在时独立重算内容哈希、比对 Receipt 的 effectEvidence、业务未接受、12 terminal error/executor/finished_at 等；Receipt 0 且仍 12 running 返回 `NOT_YET_CLOSED`，不虚报完成。
4. 专项覆盖未关闭、合法完整关闭、Receipt 哈希/效果/业务接受/Run 部分终态/副作用增量漂移；任何未知冻结。
5. 有界累计 W5c3–W5c5e 与相关合同测试；隔离库若启动则停用。
6. 浏览器只读计划/整组入口，页面不能替代正式 Receipt 与 DB Run 审计。
7. 一致性与风险：审计器不提供关闭权，真实执行必须先严格 24h、完整拓扑、新方案/唯一 key 与事务门；审计后还需正式定义退休、direct successor，A0-V/BG-00 不因闭组直接 GREEN。
8. verification 先落盘提交，再 CAS 同步 docs/AOS 项目开发上下文与 Prime 独立受管记忆、读回。
9. 下一波 W5c5f：补真实关闭前独立全机/权威租约门或其他安全研发债；到线后再另立真实关闭执行方案。

m1 单写不 push；不读商城源行；旧 attempt 不补跑；dev-org 零 canary；230 L0 挂起，未知结果冻结。
