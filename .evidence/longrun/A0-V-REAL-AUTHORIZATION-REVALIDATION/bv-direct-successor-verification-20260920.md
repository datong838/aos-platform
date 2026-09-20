# BU 正式退休与 BV direct successor verification（2026-09-20）

## 1. 结论

`BV_DIRECT_SUCCESSOR_GREEN`。本波按六步方案正式退休BU，并创建、启用、注册和切换BV；未读取商城
源数据，未创建业务attempt，未写负租户，未启动18181 API或snapshot worker，未手工调用
`run_definition`。

## 2. 方案执行与偏差

- HEAD基线 `1681695a`；严格按plan、执行、verification、commit边界串行推进。
- BU唯一attempt `617da078-f4ef-4ad9-9ac6-bd764468fa67`已是failed rev4，原因
  `RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev130 disabled，未重发。
- 默认系统Python加载到非项目Alembic，首次约束测试在加载conftest时失败、测试逻辑未运行；改用仓库
  `services/aos-api/.venv/bin/python`后专项及完整测试通过。该偏差没有访问或修改运行库。
- 主机进程窄过滤只产生当前查询进程自身PID；以状态文件、精确PID 15565和监听端口交叉确认唯一
  Runtime Host在线、第二Host=0、18181 listener=0，未启动第二实例。

## 3. BU正式退休

- BU installation/generation：`d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895` /
  `cb8ace71-ba8d-4e08-816b-8d6bbc0f0281`；原Host PID 10997一次SIGTERM后正常退出，读回binding
  rev7/epoch4 disabled/fenced/desired enabled与3/3 resources released。
- disable operation `55fab898-08ac-4548-9f07-a3e1a40485e9`；fence Receipt
  `88621327-9fb6-40d3-8eef-3a3b8e4e3c44`，content hash
  `sha256:23c463895561a6dbaa13d4aca9c5c57c853c8c04c5a18148c61192b178d02edf`。
- detach Receipt `b071b45a-1e66-4898-b79c-49f1fdcd69ea`，content hash
  `sha256:1eba5bd30d384de6ab165e9a617c7963fda5216775506d0341adfd1b63488163`。
- 最终BU binding rev9/epoch5 disabled/fenced/desired disabled；九路legacy rev188/group215。

## 4. BV lifecycle与cutover

- BV installation/generation：`2b1aa826-b595-40d4-aeb2-9a7ce9d33c36` /
  `e8a5b32b-9a29-41bf-9c7f-87c7cd96b359`；lock
  `sha256:5b994767e0abd7c6138b611e96dae1948ff1812dd02aeb23ad38b229280eb73f`。
- prepare/verify/configure/enable operation：`d5764616-1ee0-4cd8-b7a6-8d52350a6d77`、
  `491bc565-9113-4967-855b-0aa70098022d`、`0304d863-bd69-42ea-be1d-663c9c39e5d5`、
  `adb990cd-3786-4b0b-97be-76daef954683`，均succeeded。
- configuration `b59d1502-501b-46ae-ba80-80466017cacd` /
  `sha256:4525829c23f4afbd01adcaafef57648c80c8a4bbd984a6125af6a3e38a5ba3c6`。
- registration Receipt `9eef2d1c-dd56-4aa8-87e5-04618e2bccc7`，request hash
  `sha256:c1287e7de0fae8ad7c040895caed3b792d33797be27432f0dbb2525d24e7ef8c`，content hash
  `sha256:8e6552847670bdbbda21973ba20d7261d0b2be0d736df6acb300733430b252d1`。
- cutover operation `e8ab9b59-d00e-43d5-9eef-2e3e0da06a37`；prepare/pause/commit/validate/resume
  Receipts依次为 `2c55cdad-066b-493c-8448-7c9aae5d9e67`、
  `714fa35c-1541-4d75-9cfe-f4f831525d60`、`db6dd62e-e202-464d-bc80-579146148537`、
  `7e1a6b24-40a2-4ec8-bcaf-67d8172700d8`、`24877837-5125-49cc-8595-5b5174fdd275`。
- 对应content hash依次为 `sha256:d1e39e473e4136c3011ac13a69b9bd11be92fd90ec0939d20cf0e99c5c9821eb`、
  `sha256:721423f63b8774e51508a2bc00163f6d59a5eff7dfa2e7558481053fd6f16c93`、
  `sha256:6f1ab10b842d5079c5bc91d70da8949fdf28816e6f76299e8b5717f179f8895b`、
  `sha256:bded46a6d9b448343b0752abeb11221faaa9aaa8dc9dc4377e7b8acc9b486ae3`、
  `sha256:96fbd188325d9aa232d0320abc6175607b2618868b261b4df409f04b345d70b2`。
- 最终BV binding rev6/epoch3 enabled/unfenced/ready；九路extension rev189/group216。

## 5. 健康与零副作用

- 唯一外置Host PID 15565，状态文件liveTargets仅BV；第二Runtime Host=0、18181 listener=0、
  snapshot worker=0。
- 只读repeatable-read健康观察从renewals=5到17，target delta=12，35 samples；三资源始终pending、
  未释放、未过期，最终expires_at `2026-09-20T15:49:24.239765Z`。
- definition rev130 disabled；BV attempt=0；全局running attempt=0、unresolved=0、runtime pending=0、
  canary=0。
- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、
  `ecom_link=0`、projection pending=0。

## 6. 验证与下一波

- 新增逻辑仅为BU正式退休、BV固定边界包装器与只读健康观察器，生产实现未修改；测试锁定failed
  boundary、detach、lifecycle、registration、cutover和repeatable-read观察，均禁止 `run_definition`。
- `py_compile`与 `git diff --check` 通过；完整约束测试 `61 passed`。测试退出后的既有JDBC cleanup
  closed-stream日志仅为退出期告警，不影响pytest成功退出且不产生运行库写入。
- 下一波：先落 `BV saved-snapshot recovery` plan；保持当前唯一Host PID 15565在线，证明第二Host=0、
  18181=0、snapshot worker=0，再按纯HTTP transfer rev131 / recovery43 / definition rev132 enabled、
  关端口后自然worker与terminal pause rev133规则串行执行。
