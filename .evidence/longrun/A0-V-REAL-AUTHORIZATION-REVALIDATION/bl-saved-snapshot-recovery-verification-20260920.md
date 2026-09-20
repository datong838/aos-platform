# BL 保存快照恢复验证（2026-09-20）

## 结论

BL 保存快照波已按 fail-closed 边界完成。全程未读取商城源数据、未调用 `run_definition`、未创建
第二 attempt。最终 definition rev118 disabled，唯一 attempt
`06352972-8c80-4291-aece-2474209e6a76` 正式为 revision46
`abandoned / ATTEMPT_LEASE_EXPIRED / null`。

## 冻结输入转移

- 起点为 BK definition rev115 disabled，hash
  `sha256:ffd4f2afc20c438ffa0820cfbb9ac6068051a6cb641069c67d3b18c2ff840735`。
- transfer 生成 BL rev116 disabled，hash
  `sha256:055567a4a613acc1b4f50208d1018a594b297181c51e741ec280907a88c0df67`。
- recovery rev38 的 content hash 为
  `sha256:9f81de0cdf898e3ea316c9d58ba20c95103741c1401af771b2379fe9ced22be7`，
  request hash 为 `sha256:b35f209679afdec4ad5e0eb6eb41f8388613322c6446dc11bfc33fb98996ade1`，
  input manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`。
- rev117 enabled hash 为
  `sha256:dff8a28de943d8bd7c29b47b897933de802438f82bf1ab7cf5c47a6bc2fea4a0`；
  prepare、schedule-ingest、controls、transfer、renew、enable 的 sourceReads 均为零。

## 唯一自然 attempt 与观察窗

- 纯 HTTP 先行读回 Cron=false、snapshot worker=false、进程内 Runtime Host=false；18181 关闭后释放。
  启动自然 worker 前外置 Host 恰为一个，第二 Host=0。
- 唯一 attempt 于 `2026-09-20T07:17:39.869311Z` accepted；operation key
  `snapshot-group-completion:c5ff1926-45b0-56de-b6b3-07d5b7d053a1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。
- 同一 supervisor 按 50 秒只读采样到 revision44。07:39Z 后受保护 credential reference 文件被外部
  移除，外置 Host 以 `HOST_RUNTIME_FAILED` fail-closed，worker 报 `RUNTIMEERROR` 后停止；三类进程均为零。
  该未知业务边界未被重发。
- 满 accepted_at 起算 1800 秒、Lease 已过期且零副作用后，既有
  `ExpiredSignedReadAttemptRecovery` Owner 单次回收同一 attempt；completed_at 为
  `2026-09-20T07:48:07.270814Z`，revision46 `abandoned / ATTEMPT_LEASE_EXPIRED / null`。
- 随后用原 `PipelineSnapshotScheduleDefinitionOwner(controls=None)` stop-only transition 将 rev117
  精确推进为 rev118 disabled；hash
  `sha256:70b863215c256434bbcabce04b27c54e9038f2ab2ff362ed145924bec78f079e`。

## 最终数据库边界

- attemptCount=1；十二 Run 仍 running，succeeded=0、failed=0；十二 Dataset Receipt 保留。
- relationship=1、link command=1、linkCount=1168；Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、retirement=0。
- BL installation `ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc` / generation
  `116d12fc-93bc-4071-a973-fdc6830ea8b1`，九路 route rev162/group189；三资源仍 live；
  `dev-org/dev-project` canary=0。
- credential 与旧签名运行目录丢失未被擅自重建；下一波不得在该依赖未形成新 plan 与验证前启动 Runtime Host。

## 自测与一致性

- BL saved recovery、terminal supervisor、attempt guard、expired recovery、terminal pause 与 snapshot API
  相关测试通过。
- Python 编译、`git diff --check` 与精确 staged 文件复核通过后提交。
- 实现与补充方案一致：唯一 attempt、1800 秒边界、既有过期 recovery Owner、stop-only Definition Owner、
  不读源、不重发、不启动第二 Host。
