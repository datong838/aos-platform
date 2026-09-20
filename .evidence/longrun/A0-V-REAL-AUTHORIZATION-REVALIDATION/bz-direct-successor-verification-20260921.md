# BY 正式退休与 BZ direct successor verification（2026-09-21）

## 1/6 plan 与基线

`BZ_DIRECT_SUCCESSOR_GREEN`。HEAD 基线 `0e08e1e0`；BY 唯一 attempt
`72876c75-a853-488a-b1e6-4c334b635f91` 为 failed rev4，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev142 disabled、recovery46。
本波未读取商城源数据，未创建业务 attempt，未写负租户，未启动 18181 API 或 snapshot worker，未调用
`run_definition`。

## 2/6 BY Host 释放与正式退休

- BY installation/generation：`ed64db1a-45eb-442e-8f1b-49ed899731dc` /
  `01f99334-0515-4c73-b442-a293709b3cc2`；原 Host PID 29455 一次 SIGTERM 后正常退出，读回 binding
  rev7/epoch4 disabled/fenced/desired enabled 与 3/3 resources released。
- disable operation `53104614-eeaf-4c87-a5fa-97f0e518f207`；fence Receipt
  `fbe1da6f-afec-443b-ac2c-f9bcfd255bc6`，content hash
  `sha256:24f34d451f4d9bb06e49c23d5aecef2b16fe147bf69b1a7fb303338124cb8086`。
- detach Receipt `476431d3-9cb4-4e5f-bd4b-02ac2c9fd978`，content hash
  `sha256:d65a5f35ed1e32e2db5e71e93e2a201eff195fe8e0ce6a859cceee468da3dbcb`。
- 最终 BY binding rev9/epoch5 disabled/fenced/desired disabled；九路 legacy rev200/group227。

## 3/6 BZ 创建与 lifecycle

- BZ installation/generation：`9b30837c-da4d-4cfd-b438-de40aa5e3d7a` /
  `6f1e6e77-24aa-4052-9102-88e4a432fe55`；lock
  `sha256:710bd45e92ed91c1e9a634e12eb4bdd8d9a4c8cee32191537dcd62c929e277af`。
- prepare/verify/configure/enable operation：`71d642ec-f53a-46f2-94b7-9500babfc594`、
  `61d1710d-8219-4fd1-bd69-9ede5aedb65f`、`7fcccaac-c2fe-44f2-b4c7-2d6e8892bd1b`、
  `50c0d4d3-3812-4f57-9eaf-c8f84a38a1ae`，均 succeeded。
- configuration `cba5179d-e82a-4c58-87b4-3aecc33579ed` /
  `sha256:c7c9f75c2737a4dfc30cfec6ac7b87275d5e42b107227b03fcdbc99f61f3772c`；最终 lifecycle
  binding rev4/epoch3 enabled/ready，3/3 live resources。

## 4/6 注册与九路 cutover

- registration Receipt `cff389dd-d5ae-43d8-89d6-2162f838ff04`，request hash
  `sha256:f87e9a8b88c3ca7aeb518e4c23fa6a075fc4aaf31810d023fa62e377ec287c7b`，content hash
  `sha256:32835f1e86a7e479698d6a214ef53f0f0dda2058e34c084b7879d7e18ca04508`。
- cutover operation `76130027-8f29-4eaf-bd2f-ca21863b13e1`；prepare/pause/commit/validate/resume
  Receipts 依次为 `52be8b70-2781-4444-93ab-631697d4993b`、
  `8f788ba7-c1c4-4bdc-89e2-eea57dfe8538`、`a6a1c792-c2d0-4988-b40c-3d570b3318b2`、
  `d21815e1-8ab8-4799-99f0-00b3d7dd9d96`、`d6471364-3e6c-4936-ba5e-b574f805553c`。
- 对应 content hash 依次为 `sha256:a0c730b45a88b8f31e5a3aadac61bd0d807f3af49376776bcd761131a5d4930a`、
  `sha256:1d28b3f61392019eab357558d6edc990d270ec98355932026b74c2c3c3d576d8`、
  `sha256:2a3468ecfe365ae519771f81c2f20cf101a66daf0cd465a345b4604c0f960a75`、
  `sha256:ba81706747a0ae0de5a3c59b3c81c74afb2fe27b7454cb7136ac720f9f96211d`、
  `sha256:09a22a042955afe65408396bda8368206dba02062e3b6245d49dc66ade69be1b`。
- 最终 BZ binding rev6/epoch3 enabled/unfenced/ready；九路 extension rev201/group228。

## 5/6 唯一 Host 与健康观察

- 唯一外置 Host PID 31607，状态文件 liveTargets 仅 BZ；第二 Runtime Host=0、18181 listener=0、
  snapshot worker=0。
- 只读 repeatable-read 健康观察从 renewals=3 到 15、last sequence=16 到 28，target delta=12，
  36 samples；三资源始终 pending、未释放、未过期，最终 expires_at
  `2026-09-20T17:55:17.306536Z`。
- definition rev142 disabled；BZ attempt=0；全局 running attempt=0、unresolved=0、runtime pending=0、
  canary=0。

## 6/6 验证与下一波

- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、`ecom_link`=0、
  projection pending=0。
- 新增逻辑仅为 BY 正式退休、BZ 固定边界包装器与只读健康观察器，生产实现未修改；测试锁定 failed
  boundary、detach、lifecycle、registration、cutover 和 repeatable-read 观察，均禁止 `run_definition`。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行 BZ saved-snapshot
  recovery：保持 PID 31607 在线，证明第二 Host=0、18181=0、snapshot worker=0，再按纯 HTTP transfer
  rev143 / recovery47 / definition rev144 enabled、关端口后唯一自然 worker 与 terminal pause rev145 规则串行执行。
