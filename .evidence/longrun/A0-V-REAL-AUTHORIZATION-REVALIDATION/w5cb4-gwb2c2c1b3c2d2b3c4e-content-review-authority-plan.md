# d2b3c4e 内容评审宿主同源权威方案

上位：231-5 §9、BG00gw d2b3c4e。d2b3c4d 已让命令显式判别来源；宿主 `_artifact_authority` 仍严格要求旧可读形状及四个 `ArtifactRevision`，`_task_brief_authority` 仅比较四来源，`_issue_authority`/`_issue_eval_authority` 只证明内容专属 Issue/Eval 和人工事件，尚未将其与原 Stage/Review Receipt 串成同截面。

## 本波文件顺序

1. `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`：复用现有可销毁 PG 的原内容结果消费，用一个已持久化的单原 `Artifact` 做新来源 Review 命令。先 RED `_artifact_authority`，断言其返回当前内容 Artifact，错原 Artifact hash/租户拒绝。该 fixture 只是可控机制输入，不能充当原 Stage Owner、人类决定或正式 G2。
2. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：只在显式 `accepted-stage-v1` 分支校验可读 Artifact 的精确字段、canonical hash、单个原 `Artifact` 持久行；旧四 `ArtifactRevision` 分支字节和拒绝规则不变。
3. 在同一可销毁 PG 另做 v3 Brief、原 Stage/Review Receipt、内容 EvalReport/ReviewIssue、独立人工 actor 的正反测试，逐项 RED 后最小接原读者。`revalidate` 必须在同一事务同一 current cutoff 重读所有 Owner；若任何一段缺源，仍失败关闭。
4. 接 `execute/verify_receipt`、feedback 和原 Run/Task ACCEPT/RETURN 终态；重复与未知结果走只读对账。专项与相邻回归、浏览器禁入、方案复审、verification 和 m1 精确提交，随后同步 01/06/Prime/D-waves。

当前真实库只读；不启 Host/worker/Provider，不改 Growth1.13 签名候选，不读商城源、不重放旧 12 Run、不手工 Run、不碰230 L0。正式 G2 producer/受限身份/八配置/assignment/绑定缺失只限制当前实例正向，不影响受控读者研发。
