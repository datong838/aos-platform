# R19 FDE S1～S3 交付证据

- 分支：`w1-aip`
- 代码提交：`b4941e372edabeb709c6e607eaea4895267a4cb2`
- 正向租户：`org-org/dev-project`
- 负向 canary：`dev-org/dev-project`
- 交付状态：`CODE_GREEN`

## 已交付

1. FDE S1 需求规范化、S2 opaque Secret 引用草案、S3 Niushop AdapterPack 文件证据探测；
2. canonical Task + draft PlanRevision 创建，不自动批准、不自动启动；
3. exact S1～S3 Run 通过 `CanonicalTaorRunner` 生成 Artifact/Checkpoint/timeline；
4. Preview、Session、Run execution 三条 API 与确定性 OpenAPI；
5. 非法 Secret payload、未知平台、缺失映射、错误 Run 类型和租户隔离均失败关闭。

## 验证

- R19 与累计组合：`50 passed`
- AIP 全量：`1230 passed, 106 warnings`
- Python compileall：GREEN
- `git diff --check`：GREEN
- OpenAPI：`2543 paths / 1974 schemas / 4311 unique operation pairs`
- 主租户与 canary Preview：均 HTTP 200，tenant envelope 不串租；状态为 `external_required`，`onlineVerification=not_started`

## 边界与已知风险

- Preview 路由自身未写业务数据、未执行 Pipeline、未调用 Provider；
- 启动完整 API 进程时出现系统既有 JDBC/元数据/bootstrap/cron 初始化日志，因此本证据不宣称“主进程启动无外部副作用”；
- 未读取 Secret payload，未读取 `.evidence/aip/auth-storage-state.json`；
- 未修改 migration、真实业务数据库、Workshop、`130`、authority/01/06/Prime；
- Data Owner Lease 仍为 ACTIVE，R20 若涉及受控同步或 migration，必须继续失败关闭或取得唯一 Lease。
