# W5CB4 P2g29a · RETURN 新版 Brief 冻结来源验证（2026-09-27）

- 方案先行 `m1@1a4711a6`：公共 Action 的绑定 hash 要求 frozen/ready ImpactPreview，而 Preview 不接受 draft Brief。因此不能把 P2g27 新版 draft 直接用于正式批准。
- 在原同库正式 RETURN 链上，用公共 `revise_brief` 后的 `freeze_brief` 产生第三版 frozen Brief；非超级 runtime 身份同一 scoped 快照复核原评审版→返工 draft→冻结版的 revision/hash/spec、两张公共 Receipt、ReturnDecision/原 Artifact 与理由。无直接 INSERT Brief/Receipt。旧版、伪 freeze Receipt、draft 内容漂移、非当前 head 负例拒绝。
- `ContentGenerateHostService` 返工门改为只认 frozen 的新 Brief；首次生成路径不变，P2g26 的 `revalidate/execute` 双重执行禁入仍在。公开 Action API、Preview、真人新批准、预算和 Provider 都未启动。
- RED：缺 `require_frozen_repair_brief` 和 Host 冻结版接线均曾失败；修复后九组邻近累计 **93 passed**，`compileall`/`git diff --check` 通过，Alembic 唯一 head `a0v_106`。当前 8080/18181 保持未启；纯后端本子波浏览器不适用。
- 这是 P2g29 第一子证明，不是完整 Preview/Action 生产链。后续在同一原对象链核 ProductionContext、EvidenceBundle、EvalContract、ResponsibilityPlan、StageTemplate 与 Plan risk 是否能合法组成 frozen/ready Preview；不能将夹具直接 INSERT 的批准当作公共 Action 正向。恢复库仍 `a0v_092` 且无当前备份，`STOP_MIGRATION / STOP_CURRENT_API_AND_WORKERS`。
