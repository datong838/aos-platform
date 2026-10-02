# GW-b-2c2c1b3c2d2b3c3 生成回执来源歧视验证

- 方案：同目录 `w5cb4-gwb2c2c1b3c2d2b3c3-content-receipt-plan.md`；上位 231-5 §9。
- RED：新增测试先运行，1 failed；`ContentCapabilityReceipt.from_payload` 把原 `Artifact` 拒于旧 `ArtifactRevision` 类型门，退出 1。
- GREEN：包内 `ReadableContentArtifact` 对新分支要求显式 `sourceKind=accepted-stage-v1`、单个原 `Artifact`；旧包维持四个 `ArtifactRevision` 字段形状。回执按请求来源解析，并在完成态再次核产物来源。新分支人工评审构造在 port 前拒绝。
- 专项与相邻：`services/aos-api/.venv/bin/python -m pytest -q` 运行 capability budget、content review pending、step owner、authority feedback 四文件，`64 passed, 7 warnings`，退出 0。`py_compile` 三个变更文件、`git diff --check` 均退出 0。
- 浏览器只读：当前 `http://127.0.0.1:8434/aip/skill-publish` 仍显示 37 项仅评测、0 发布，三类当前精确发布候选阻断，“发布此修订” disabled，侧栏无电商工作台入口。包内改动不构成 UI 或当前实例正向验收。
- 边界：`execute_content_capability` 的 accepted-stage 仍在 port 前拒，`ContentReviewRequest` 同样拒；生成 Host、正式 G2 Skill Eval/发布、OIDC、八配置、Host 身份/assignment/binding、Growth1.13 正式发布仍未齐，真实首链未发生。未触及真实库、Host/worker/Provider 或外部效果。
