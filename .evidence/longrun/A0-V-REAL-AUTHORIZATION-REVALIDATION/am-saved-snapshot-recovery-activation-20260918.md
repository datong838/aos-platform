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

## 12:49–12:52Z 自动接续观察

- 自动接续任务已从已退休 AL 纠正为当前 AM attempt，不改变 5 分钟频率和本任务串行边界。
- attempt 从 revision11 连续推进到 revision26；事件历史为 1 次 `attempt_accepted` 加 25 次连续
  `attempt_heartbeat`，最后事件发生于 `2026-09-18T12:51:29Z`，未见跳号、失败或第二 attempt。
- 12 个 Run 仍为 running；dataset Receipt=12、relationship=1、link command=1、linkCount=1168、retirement=0、
  Store links=0、projection pending=0、live resources=3、dev-org canary=0。
- 原 link idempotency key 对应 `ecom_ingest_receipt` 仍为空，authoritative Store link outbox 仍为空；因此当前是
  Store 尚未提交的已知边界，不是未知结果，禁止重发。
- 浏览器复验：AOS v1.6.5 首页与主导航可加载；“电商工作台”仍显示“正在读取工作台目录”，所以浏览器门禁继续保持
  NOT GREEN，待 attempt 终态和 complete-group disable 后复验。

## 12:59–13:01Z 自动接续观察

- AM 仍只有 attempt `7d6cc3aa-881d-4aff-ac30-58978d06e85d`，已推进至 revision42；最新 heartbeat
  `2026-09-18T12:59:35Z`、lease `13:01:34Z`，防休眠进程仍存活。
- 十二 Run running、dataset Receipt=12、relationship=1、原 link command=1/linkCount=1168；retirement=0、精确
  Store Receipt=0、Store links=0、authoritative Store outbox=0、projection pending=0、live resources=3、canary=0。
- runtime status 为 `RUNTIME_HOST_ACTIVE`，仅一个 AM live target；主进程仍持有三个受管 Docker attach 子进程，数据库侧
  存在活动事务身份。日志中检出的异常属于旧 pid 的历史终止记录，不是当前 attempt 的新失败。
- 浏览器稳定加载 AOS v1.6.5 后，“电商工作台”目录终态为“暂无可见工作台入口”；继续保持浏览器 NOT GREEN。

## 13:07–13:10Z 自动接续观察

- AM 仍只有 attempt `7d6cc3aa-881d-4aff-ac30-58978d06e85d`，推进至 revision59/running；最新 heartbeat
  `2026-09-18T13:08:10Z`、lease `13:10:10Z`，未出现终态或第二 attempt。
- 十二 Run running、dataset Receipt=12、relationship=1、原 link command=1/linkCount=1168；retirement=0、精确
  Store Receipt=0、Store links=0、authoritative Store outbox=0、projection pending=0、live resources=3、canary=0。
- 复核正式实现后确认：30 秒 heartbeat/120 秒 lease 由独立守护路径续租；昂贵的 retirement/Store 阶段完成后，
  `_finish` 才在同一收口事务中关闭十二 Run 并写入 projection/retirement。因而 attempt 尚为 running 时，外部只读视图中
  “十二 Run 仍 running 且 Store/retirement/projection 为 0”符合原子可见性设计，不能据此判定停滞，也不构成重发授权。
- 浏览器稳定加载 AOS v1.6.5；“电商工作台”仍显示“暂无可见工作台入口”，继续保持浏览器 NOT GREEN；未点击
  “重新读取目录”，未改变运行态。

## 13:18–13:20Z 自动接续观察

- AM 唯一 attempt 推进至 revision80/running；最新 heartbeat `2026-09-18T13:18:46Z`、lease
  `13:20:46Z`，十二 Run 仍为 running，未出现失败、终态或第二 attempt。
- dataset Receipt=12、relationship=1、link command=1/linkCount=1168；retirement=0、精确 Store Receipt=0、
  Store links=0、authoritative Store outbox=0、projection pending=0、live resources=3、dev-org canary=0，继续符合
  running 阶段的原子可见性边界，不构成重发授权。
- runtime host 保持 `RUNTIME_HOST_ACTIVE`，只含 AM 一个 live target，三个受管容器仍附着；`caffeinate` 存活。
- AM 专项及 replacement/successor/cutover、AL 保存恢复相邻回归共 `5 passed`；7 条既有框架 warning，退出码 0。
- 浏览器稳定加载 AOS v1.6.5，“电商工作台”仍显示“暂无可见工作台入口”；浏览器门禁保持 NOT GREEN，未触发重读。

## 13:27–13:29Z 自动接续观察

- AM 唯一 attempt 自然推进至 revision97/running；heartbeat `2026-09-18T13:27:21Z`、lease `13:29:21Z`，
  未出现终态、失败或第二 attempt。
- 十二 Run running、dataset Receipt=12、relationship=1、link command=1/linkCount=1168；retirement=0、精确
  Store Receipt=0、Store links=0、projection pending=0、dev-org canary=0。继续保持原子提交前的已知边界，不重发。
- runtime host 仍为 `RUNTIME_HOST_ACTIVE`，仅含 AM 一个 live target；三个受管容器与 `caffeinate` 存活。
- 相同 AM 专项及 replacement/successor/cutover、AL 保存恢复相邻回归再次 `5 passed`，7 条既有 warning，退出码 0。
- 浏览器稳定加载 AOS v1.6.5；电商目录仍为“暂无可见工作台入口”，门禁继续 NOT GREEN，未触发重读。

## 13:35–13:37Z 自动接续观察

- AM 唯一 attempt 推进至 revision113/running；heartbeat `2026-09-18T13:35:25Z`、lease `13:37:25Z`，
  十二 Run 与既有 dataset/relationship/link command 边界不变，Store/retirement/projection 尚未原子显现，canary=0。
- 三个受管容器均为 running，未 paused/restarting/OOM/dead；只读 `pg_stat_activity` 可见受限会话仍持有事务 ID。
  当前角色按设计隐藏其 state/query/xact 时间，因此该观察只证明事务身份仍在，不能证明成功或推断具体 SQL，也不授权干预。
- 相同 AM 专项及相邻回归 `5 passed`，7 条既有 warning，退出码 0；未修改产品代码。
- 浏览器稳定加载 AOS v1.6.5 后，电商目录仍为“暂无可见工作台入口”；浏览器门禁继续 NOT GREEN，未触发重读。

## 13:43–13:45Z 自动接续观察

- AM 唯一 attempt 推进至 revision129/running；heartbeat `2026-09-18T13:43:30Z`、lease `13:45:30Z`，
  十二 Run、12 份 dataset Receipt、relationship=1、link command=1/linkCount=1168、live resources=3 保持一致；
  Store/retirement/projection 尚未显现，canary=0。
- 同一受限数据库会话继续持有事务 ID 与 161 个已授予锁，等待锁为 0；三个容器均 running、restartCount=0、
  OOM=false。该事实排除了当前锁等待和容器重启循环，但不替代终态提交证明。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning，退出码 0；未修改产品代码。
- 浏览器稳定加载 AOS v1.6.5，电商目录仍为“暂无可见工作台入口”；门禁保持 NOT GREEN，未触发重读。

## 13:51–13:54Z 自动接续观察与事务归因更正

- AM 唯一 attempt 推进至 revision145/running；heartbeat `2026-09-18T13:51:34Z`、lease `13:53:33Z`；
  十二 Run、dataset Receipt=12、relationship=1、link command=1/linkCount=1168、live resources=3 保持一致，
  Store/retirement/projection 仍未显现，canary=0。
- 容器瞬时 CPU 为 0.00%–0.01%，均仅 1 PID；同库另有持有事务 ID 的受限会话，但其 PID/锁数相对上一观察发生变化。
  进一步读取确认本次只读探针 PID 与该会话不同，但当前角色仍无法把该会话唯一绑定到 AM Worker。因此更正前两节解释边界：
  它们只能证明同库存在另一个事务，不能单独证明 AM 长事务正在执行具体 SQL；提交 `62382fc8`/`38443ec1` 的事实数字保留，
  对“AM 活跃事务”的归因由本节收窄。AM 健康仍以唯一 running attempt、连续 heartbeat/lease、容器未退出和终态记录为准。
- 相同 5 项专项与相邻回归通过，7 条既有 warning，退出码 0；浏览器稳定态仍为“暂无可见工作台入口”，
  继续 NOT GREEN，未触发重读。

## 14:00–14:02Z 自动接续观察

- AM 唯一 attempt 推进至 revision162/running；heartbeat `2026-09-18T14:00:09Z`、lease `14:02:09Z`；
  十二 Run、dataset Receipt=12、relationship=1、link command=1/linkCount=1168、live resources=3 保持一致，
  Store Receipt/link/outbox、retirement 与 projection pending 均为 0，canary=0。
- 三个容器均为隔离 runner `-I /aos/runner.py --serve`，running、restartCount=0、OOM=false。其日志驱动明确不支持
  `docker logs` 回读；因此本轮只把容器生命周期作为证据，不把无日志误作内部步骤成功或失败。
- 相同 5 项专项与相邻回归通过，7 条既有 warning，退出码 0；未修改产品代码。
- 浏览器稳定加载 AOS v1.6.5，电商目录仍为“暂无可见工作台入口”；门禁保持 NOT GREEN，未触发重读。

## 14:08–14:10Z 自动接续观察

- AM 唯一 attempt 推进至 revision178/running；heartbeat `2026-09-18T14:08:15Z`、lease `14:10:15Z`；
  十二 Run、dataset Receipt=12、relationship=1、link command=1/linkCount=1168、live resources=3 保持一致，
  Store Receipt/link/outbox、retirement、projection pending 均为 0，canary=0。
- attempt 事件表当次读取为 1 条 `attempt_accepted` 与 179 条 `attempt_heartbeat`，sequence/revision 1–180 连续，
  gap=0；没有失败事件、第二接受事件或其他状态。该事实证明状态机历史连续，不代表 Store 已提交。
- 相同 5 项专项与相邻回归通过，7 条既有 warning，退出码 0；未修改产品代码。
- 浏览器稳定加载 AOS v1.6.5，电商目录仍为“暂无可见工作台入口”；门禁保持 NOT GREEN，未触发重读。

## 14:16–14:19Z 自动接续观察

- AM 唯一 attempt 推进至 revision195/running；heartbeat `2026-09-18T14:16:51Z`、lease `14:18:51Z`；
  十二 Run、dataset Receipt=12、relationship=1、link command=1/linkCount=1168、live resources=3 保持一致，
  Store Receipt/link/outbox、retirement、projection pending 均为 0，canary=0。
- 当前 binding 仍精确为 AM installation/generation、executionEpoch=3、revision=6、ready/enabled/unfenced；最新 recovery
  仍为 revision17、previousRevision16、currentDefinitionRevision53，input manifest hash 精确匹配，未见授权漂移。
- 相同 5 项专项与相邻回归通过，7 条既有 warning，退出码 0；未修改产品代码。
- 浏览器稳定加载 AOS v1.6.5，电商目录仍为“暂无可见工作台入口”；门禁保持 NOT GREEN，未触发重读。
