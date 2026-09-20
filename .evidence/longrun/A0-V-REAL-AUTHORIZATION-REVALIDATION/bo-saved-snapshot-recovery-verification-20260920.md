# BO 保存快照恢复冻结验证（2026-09-20）

## 结论

BO 保存快照波已按 fail-closed 边界冻结完成，但不得标记为单 attempt 成功。自然 worker 在 50 秒首个
监督采样窗内创建了两个 attempt；两者均以相同 request hash正式失败，业务副作用为零。worker与
supervisor已经停止，definition 已经通过原 stop-only Owner 从 rev120 enabled推进为 rev121 disabled。
本波未读取商城源数据、未调用 `run_definition`、未重发任何未知结果。

## 冻结输入与迁移

- 起点为 BL definition rev118 disabled；transfer生成 BO rev119 disabled，hash
  `sha256:0597a6818df71a7c38a656055953aecc0a7006e043a5d73fcc1c9d9be2399181`。
- recovery rev39/hash
  `sha256:39ca604ec957db0f8a7b20fedecd11f25e3ed8d60e3cc0feea56d6568d8cc2ec`；
  request hash `sha256:44084781c5e7fe70ead9bf9c704ae65f2f4676a42028060d8f44717e0adb579e`；
  input manifest仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`。
- rev120 enabled/hash
  `sha256:6ee3a5b996c64e8b8c0eb17909d564c5037f460a02cbbf4365b9ba85022b23fa`；
  prepare、schedule-ingest、controls、transfer、renew、enable均为 `sourceReads=0`。
- replacement transfer首次暴露 policy与三类 artifact alias revision校验未同步。应用契约只允许同类型、
  同资源路径、同内容摘要的revision前进；任何路径、类型或摘要变化仍拒绝。
- schema从 `a0v_089`事务化升级到 `a0v_090`；迁移 hash
  `sha256:40ca2aab635c9d0d149d4a6afaf6c519962925aa431911120ff0b7594d48de03`。
  独立备份为 11273073 bytes/hash
  `sha256:75ae8c989ba04e22669a9827032ce63141b2a3cfbe5225c8fe136e6e9dd38158`；
  四张 authority表迁移前后 count/digest逐一相同，businessWrites=0、sourceReads=0。

## HTTP与自然 worker

- 纯 HTTP 18181读回 Cron=false、snapshot worker=false、进程内 Runtime Host=false、sourceCalls=0、
  runsCreated=0；关闭后端口释放。自然 worker启动前外置 Host=1，第二 Host=0，attempt=0。
- BO 专用薄封装使用 task `A0V-BO-SNAPSHOT-WORKER-20260920`、BO状态目录与现有 BO signed launcher；
  启动读回 Cron=false、进程内 Host=false、独立 snapshot worker=true。
- attempt `57881020-86fe-44cc-be3e-2cd90787205e`：accepted
  `2026-09-20T10:28:12.323736Z`，completed `10:28:18.347089Z`，rev2 failed，
  `RECOVERABLE_EXECUTION_EXCEPTION / RuntimeConflict`，idempotency suffix `:1`。
- attempt `9d1fc481-7eb2-426f-8b0b-65627f06ec97`：accepted
  `2026-09-20T10:28:37.363727Z`，completed `10:28:42.897999Z`，rev2 failed，
  同一终态，idempotency suffix `:2`。
- 两者 request hash均为
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。
  第二 attempt被首个50秒采样发现后 supervisor立即SIGTERM，worker return=-15，未升级SIGKILL。

## 缺陷修复与最终边界

- source claim successor校验现与 recovery authority一致，仅放行同实体同摘要 alias revision。
- snapshot worker只要一个 tick返回 `SNAPSHOT_EXECUTION_UNCONFIRMED`，即停止 serve，不再自动进入下一
  tick；正式恢复必须走退休/direct successor，不允许在原 installation内重发。
- definition最终 rev121 disabled/hash
  `sha256:e12b288fc65522b7978b439fe02d169e1367a50d44d66c6f72ff1b8def484044`。
- attemptCount=2；十二 Run仍running、十二 Dataset Receipt保留；relationship=1、link command=1、
  linkCount=1168；Store Receipt=0、`ecom_link`=0、link outbox=0、projection pending=0、retirement=0；
  三资源仍live，`dev-org/dev-project` canary=0。
- BO installation `307399a0-21bb-4d55-95b2-8b0fee238913` / generation
  `030bf59c-c998-4ee6-aedb-11d8d7d5831a`；九路 route rev168/group195；外置 Host=1，
  snapshot worker=0、supervisor=0。

## 自测、偏差与下一波

- alias transfer、source claim、worker lifecycle、迁移、definition transfer、BO wrapper与 stop-only pause
  均有回归；Python编译、Alembic single head、`git diff --check`和精确staged复核必须在提交前通过。
- 与原方案偏差：目标是唯一自然 attempt；实际在50秒窗内产生两个正式失败 attempt。因此本文件只证明
  “明确失败且零副作用后的冻结完成”，不证明唯一 attempt或业务成功。
- 下一波必须先落盘计划，再对 BO执行正式 failed terminal retirement，停止唯一外置 Host、撤销九路与
  三资源，并从 detached BO authority注册 BP direct successor。不得在 BO内再次启动 worker。
