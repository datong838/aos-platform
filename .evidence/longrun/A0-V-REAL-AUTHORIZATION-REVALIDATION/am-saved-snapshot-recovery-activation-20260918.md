# AM 保存输入恢复启动验证（2026-09-18）

## 范围

- 租户：`org-org/dev-project`；`dev-org/dev-project` 仅作隔离 canary。
- installation：`fd28d180-db24-4568-a848-101fcd3aa3c5`。
- generation：`d6bc117e-d19d-4413-beb4-02884206e290`。
- group：`c5ff1926-45b0-56de-b6b3-07d5b7d053a1`。
- manifest：`sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`。

## 已确认事实

1. `prepare/schedule-ingest/controls` 精确确认 AM 身份、12 个来源和当前 control binding；未读取商城源表正文。
2. definition 从 AL rev51 disabled 转移为 AM rev52 disabled，前代 ref 精确匹配。
3. recovery 从 rev16 续签为 rev17，Owner 同步生成 definition rev53 enabled；transfer/renew 均记录 `sourceReads=0`。
4. 自然 Worker 创建唯一 AM attempt `7d6cc3aa-881d-4aff-ac30-58978d06e85d`；没有调用 `run_definition`。
5. 2026-09-18T12:41Z 观察：attempt revision6/running，heartbeat `12:41:23Z`，lease `12:43:23Z`；12 个 Run running，dataset Receipt=12，relationship=1，link command=1、linkCount=1168，retirement=0，projection pending=0，live resources=3，canary=0。

## 锁竞争处理

自然 Worker 启动后，两次只读 `enable` 核对均在 `bundle_installation` tuple lock 上超时。两次均未产生结果文件，没有改运行态，
也没有重复 transfer/renew。按同阶段两次失败的停止规则，转为无锁只读对账；确认 definition rev53 enabled、AM binding
rev6/epoch3 ready+enabled+unfenced。`enable-result.json` 留待 attempt 终态释放 installation lock 后生成。

## 验证

- `py_compile`：通过。
- AM 保存输入专项测试：1 passed。
- AM replacement/successor/cutover、AL retirement 累计回归：5 passed。
- `git diff --check`：通过。
- 浏览器：`http://127.0.0.1:8434/` 可加载，标题为 `AOS`；工作台目录可见性仍不能据此判 GREEN，待 complete-group disable 后复验。

## 当前结论与下一波

恢复已进入唯一自然 attempt 的运行期，尚未完成完整经营链路，也未达到本波终态 GREEN。下一波保持只读守护 heartbeat/lease、
十二 Run、原 link command 的 Store 提交、retirement、projection 与 canary。attempt succeeded 后执行 `enable/inspect/disable`；
attempt failed 时先固定失败原点及未知提交边界，禁止猜测重发。
