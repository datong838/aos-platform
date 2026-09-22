# DE 保存快照恢复正式终态验证（2026-09-22）

## 结论

`DE_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`c8ff272f-9fd2-4b54-aef2-87df454e0251` 正式 failed **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition 已推进到 rev235
disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从 DD
installation `6e05658b-5d0a-40ae-ab8e-81fcca5269db` rev232/recovery76 转入 DE。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `232d4bca`；DE `5d993078-18ec-4302-9286-7081a1463cc0` / generation
`f5181ad4-e304-4533-aa4a-0f30b3c6dac3`，binding rev6/epoch3 ready、九路 rev294/group321、
唯一 Host PID 74459；definition 为 DD rev232 disabled、recovery76、attempt=0，12/12 与
零副作用。configuration rev1 已引用 RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

check/serve Cron=false、snapshot worker=false、进程内 Host=false；prepare/schedule/controls
各 12 项；previewHash `sha256:af436b5ac5a5c3448714d7494c9d7ded4622ad7ac900f5aaeaa2df459ea5b3c9`；
随后 18181 SIGTERM，Host 74459 保持唯一。

## 3/6 冻结输入转移

transfer rev233/`sha256:5d9313c462e5b3ecdf7c4cf5e5b53abe44b22f0f52fc8daeeadb14af1b1803b3`；
renew recovery77/`sha256:da03bcf65d367b30fc1c86b83d687ea90d752d306c353c866c4c9dff4d66668c`；
enable rev234/`sha256:da78b59f6ccb513ab562a420aff20d27f415c364b3ed696b90e5e7f81248cc85`；
sourceReads=0。

## 4–5/6 唯一自然 attempt

enable 后唯一 worker 经 supervisor 启动；唯一 attempt `c8ff272f…` 自然 terminal（attemptCount=1）；
未启动第二 worker。accepted_at `2026-09-22T02:16:33.619982Z`；幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`；request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。Lease
`A0V-DE-SNAPSHOT-WORKER-20260922` 已登记（docs，不进本 commit）。终态 revision=**5**
（同 CJ/CS 路径，非 DD 的 rev4）。

## 6/6 终态

pause-terminal 经 exact guard 冻结 FAILED_FREEZE_BOUNDARY，生成 rev235 disabled/hash
`sha256:e081e5cb013341b2c8d775a4a8406544cacf4c3bf0b9bb2e6caf3882ba2d5cd9`。
12/12、Store=0、ecom_link=0、canary=0、18181=0，Host 74459 仍在。下一波：DE 正式退休与
DF direct successor；退休 preflight 前不得创建 `replacement-df`。
