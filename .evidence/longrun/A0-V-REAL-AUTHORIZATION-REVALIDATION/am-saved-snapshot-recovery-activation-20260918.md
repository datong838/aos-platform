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

## 14:25–14:28Z 自动接续观察

- AM 唯一 attempt 推进至 revision212/running；heartbeat `2026-09-18T14:25:27Z`、lease `14:27:27Z`；
  十二 Run、dataset Receipt=12、relationship=1、link command=1/linkCount=1168、live resources=3 保持一致，
  Store Receipt/link/outbox、retirement、projection pending 均为 0，canary=0。
- 复核正式连接实现：web/runtime/directory 为三种独立最小权限身份，没有额外管理连接。本轮不为读取其他会话 SQL/wait
  而提升权限；继续只以权威 attempt、当前 authority、容器生命周期和正式终态记录判断。
- 相同 5 项专项与相邻回归通过，7 条既有 warning，退出码 0；未修改产品代码。
- 浏览器稳定加载 AOS v1.6.5，电商目录仍为“暂无可见工作台入口”；门禁保持 NOT GREEN，未触发重读。

## 14:33–14:36Z 自动接续观察

- AM 唯一 attempt 自然推进至 revision232/running；heartbeat `2026-09-18T14:35:34Z`、lease
  `14:37:34Z`，completedAt 仍为空。十二 Run、dataset Receipt=12、relationship=1、link command=1/linkCount=1168、
  live resources=3 保持一致；Store Receipt/link/outbox、retirement、projection pending 均为 0，canary=0。
- attempt 事件表共 232 条，sequence 1–232 连续，其中仅 1 条 `attempt_accepted`、0 条 `attempt_failed`，其余为
  连续 heartbeat；未出现重复接受、失败事件或未知重发边界。
- runtime host 状态文件仍为 `RUNTIME_HOST_ACTIVE`，只含 AM 一个 live target，`caffeinate` 存活。此前观察的三个短生命周期
  runner 容器已不在当前 `docker ps` 清单中；当前两项 PostgreSQL 基础服务保持 running，其中开发库为 healthy。该容器清单变化
  本身既不证明 Store 已提交，也不证明 attempt 失败，终态仍以权威 attempt 与正式提交记录为准。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning，退出码 0；未修改产品代码。浏览器稳定加载 AOS v1.6.5，
  电商目录仍为“暂无可见工作台入口”；门禁保持 NOT GREEN，未触发重读。

## 14:42–14:46Z 自动接续观察

- AM 唯一 attempt 自然推进至 revision252/running；heartbeat `2026-09-18T14:45:40Z`、lease
  `14:47:40Z`，completedAt 仍为空。事件 sequence 1–252 连续，仅 1 条 `attempt_accepted`、0 条
  `attempt_failed`、0 条 `attempt_succeeded`，没有第二受理或未知重发边界。
- 沿正式 group 表复核：members=12、running Run=12、冻结 input=1、累计 recovery Receipt=17、AM live
  resources=3、dev-org canary=0。runtime host PID 99810 仍存活，状态文件持续刷新且只含 AM 一个 live target；
  `caffeinate` 存活。
- 本轮首个只读组合查询使用了已不存在的旧表名 `extension_runtime_execution_run`，事务按数据库语义回滚且无写入；随后通过
  现场 schema 与正式实现确认 Run 权威表为 `meta_schedule_run` 并完成上述复核。该命令漂移不改变 AM 状态，也不授权干预。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning，退出码 0；未修改产品代码。浏览器稳定加载 AOS v1.6.5，
  电商目录仍为“暂无可见工作台入口”；门禁保持 NOT GREEN，未触发重读。

## 14:52–14:54Z 自动接续观察

- AM 唯一 attempt 自然推进至 revision268/running；heartbeat `2026-09-18T14:53:47Z`、lease
  `14:55:47Z`，completedAt 仍为空。事件 sequence 1–268 连续，仅 1 条 `attempt_accepted`、0 条
  `attempt_failed`、0 条 `attempt_succeeded`。
- group 仍为 members=12、running Run=12；AM live resources=3、dev-org canary=0。正式续签后的 budget/runtime
  policy rev8 与 model/route rev7 有效窗止于 `2026-09-19T11:48:51Z`，距离本次观察约 21 小时，不接近 AL 曾发生的
  治理到期边界；本轮没有续签或修改任何策略。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning，退出码 0；未修改产品代码。浏览器稳定加载 AOS v1.6.5，
  电商目录仍为“暂无可见工作台入口”；门禁保持 NOT GREEN，未触发重读。

## 14:58–15:01Z 连续执行观察与 Docker context 更正

- AM 唯一 attempt 自然推进至 revision280/running；heartbeat `2026-09-18T14:59:52Z`、lease
  `15:01:52Z`。事件 sequence 1–277 的阶段性读取连续，仅 1 条 accepted、0 条 failed/succeeded；members=12、
  running Run=12、succeeded Run=0、live resources=3、dev-org canary=0。
- runtime host PID 99810 仍存活并持续刷新状态文件，且持有三个 `docker --context colima-aos-extension start --attach`
  子进程。切换到正确 context 后，三个 runner 均为 running、未 paused/restarting/OOM/dead，启动时间保持
  `2026-09-18T12:11:01Z` 至 `12:11:03Z`；当前各 1 PID，瞬时 CPU 为 0%，恢复数据库瞬时 CPU 约 11.6%。
- 更正 14:33–14:36Z 一节的容器解释：当时的 `docker ps` 使用默认 Docker context，只能说明默认 context 中看不到三个
  runner，不能说明 runner 已回收。正确 `colima-aos-extension` context 证明三者持续运行；该更正不把容器或数据库活跃度
  冒充具体 SQL、Store 提交或 attempt 成功证明。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning，退出码 0；浏览器稳定加载 AOS v1.6.5，电商目录仍为
  “暂无可见工作台入口”，门禁保持 NOT GREEN，未触发重读。

## 15:01–15:05Z 连续执行下一波

- 未等待定时任务，上一波提交后直接进入本波。AM 从 revision284/running 连续推进至 revision290/running；最新
  heartbeat `2026-09-18T15:04:55Z`、lease `15:06:55Z`，completedAt 为空。十二 Run 始终全部 running。
- 中间事件读取为 sequence 1–287 连续，仅 1 条 accepted、0 条 failed/succeeded；正确
  `colima-aos-extension` context 下三 runner 均 running、未 restarting/OOM/dead。
- 一次跨周期只读命令在工具 30 秒输出窗结束时尚处模块初始化，随后确认没有遗留探针进程，并重新读取权威 attempt；该观察
  未写数据库、未重复业务执行，也未改变 AM 状态。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning；浏览器稳定态仍为“暂无可见工作台入口”，门禁 NOT GREEN，
  未触发重读。测试与浏览器结果均未被当作真实经营闭环完成证明。

## 15:05–15:10Z 持续只读监视波

- 在同一任务内启动只读监视会话，未等待定时任务；AM 连续输出 revision291 至 revision299，最新 heartbeat
  `2026-09-18T15:09:29Z`、lease `15:11:29Z`，全程 state=running、completedAt 为空。
- 阶段性权威事件读取为 sequence 1–287 连续，仅 1 条 accepted、0 条 failed/succeeded；正确
  `colima-aos-extension` context 下三 runner 均 running、未 restarting/OOM/dead。没有启动第二业务执行或写入探针。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning；复用已打开的浏览器页复验仍为“暂无可见工作台入口”，
  门禁 NOT GREEN，未触发重读。监视会话在本波提交时继续运行。

## 15:10–15:15Z 持续只读监视波

- 同一只读监视会话连续观察到 AM revision300 至 revision310；最新 heartbeat `2026-09-18T15:15:03Z`、
  lease `15:17:03Z`，各次均为 running、completedAt 为空，没有中断或第二观察进程。
- 本次观察区间未出现终态，因此未执行 `enable/inspect/disable`，也未改变 definition、Run、Store 或资源状态。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning；复用浏览器页复验仍为“暂无可见工作台入口”，
  门禁 NOT GREEN，未触发重读。监视会话在本波提交时继续运行。

## 15:15–15:23Z 持续只读监视波

- 首段监视器按预设 30 次读取正常退出，末端 revision311/running；同一任务立即续建只读监视器，连续观察
  revision312 至 revision325。最新 heartbeat `2026-09-18T15:22:36Z`、lease `15:24:36Z`，均为 running。
- 监视器轮换只读取 attempt，不创建业务 attempt、Run、Receipt 或 Store 写入；本区间未出现 succeeded/failed，因而没有执行
  收口或失败退休动作。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning；复用浏览器页复验仍为“暂无可见工作台入口”，
  门禁 NOT GREEN，未触发重读。第二段监视器在本波提交时继续运行。

## 15:23–15:28Z 持续只读监视波

- 第二段监视器连续观察 revision326 至 revision332 后按预设长度正常退出；同一任务立即续建第三段监视器，连续观察
  revision333 至 revision336。最新 heartbeat `2026-09-18T15:28:09Z`、lease `15:30:09Z`，均为 running。
- 监视器轮换期间未出现 succeeded/failed，没有触发 definition、Run、Store 或资源写入；只读监视链连续。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning；浏览器仍为“暂无可见工作台入口”，门禁 NOT GREEN，
  未触发重读。第三段监视器在本波提交时继续运行。

## 15:28–15:34Z 持续只读监视波

- 第三段只读监视器连续观察 AM revision337 至 revision348；最新 heartbeat `2026-09-18T15:34:14Z`、
  lease `15:36:14Z`，各次均为 running、completedAt 为空。
- 本区间未出现终态，未执行 `enable/inspect/disable`，也未改变 definition、Run、Store、资源或治理策略。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning；浏览器仍为“暂无可见工作台入口”，门禁 NOT GREEN，
  未触发重读。监视器在本波提交时继续运行。

## 15:34–15:43Z 持续只读监视波

- 第三段只读监视器连续观察 AM revision349 至 revision352 后按预设长度正常退出；同一任务立即续建第四段监视器，
  连续观察 revision354 至 revision364。最新 heartbeat `2026-09-18T15:42:18Z`、lease `15:44:18Z`，
  各次均为 running、completedAt 为空。revision353 未出现在监视器的变更输出窗口中，不代表权威状态缺失或执行中断。
- 本区间未出现 succeeded/failed，未执行 `enable/inspect/disable`，也未改变 definition、Run、Store、资源或治理策略；
  第四段监视器继续运行。
- 相同 5 项 AM/AL 专项与相邻回归通过，7 条既有 warning；复用浏览器页复验仍为“暂无可见工作台入口”，
  门禁 NOT GREEN，未触发重读。测试与页面可见性均未被当作真实经营闭环完成证明。

## 15:43–15:50Z 持续只读监视波

- 第四段只读监视器继续观察 AM revision365 至 revision373 后按预设长度正常退出；同一任务立即续建第五段监视器，
  连续观察 revision375 至 revision379。最新 heartbeat `2026-09-18T15:49:53Z`、lease `15:51:52Z`，
  各次均为 running、completedAt 为空。revision374 未出现在变更输出窗口，不代表权威状态缺失或执行中断。
- 本区间没有 succeeded/failed，未执行 `enable/inspect/disable`，也未改变 definition、Run、Store、资源或治理策略；
  第五段监视器继续运行。
- 相同 5 项 AM/AL 专项与相邻回归再次通过：5 passed、7 条既有 warning。浏览器稳定加载 AOS v1.6.5，
  电商目录仍为“暂无可见工作台入口”，门禁 NOT GREEN，未触发“重新读取目录”。

## 15:50–15:56Z 跨旧失败点持续观察

- 第五段只读监视器连续观察 AM revision380 至 revision391；最新 heartbeat `2026-09-18T15:55:56Z`、
  lease `15:57:56Z`，各次均为 running、completedAt 为空。AM 已自然跨过 AL 曾因治理过期而失败的 revision382，
  当前正式续签治理有效窗仍充足，未出现相同失败信号。
- 跨过旧 revision 只证明恢复链路继续推进，不等于 attempt、十二 Run 或经营闭环成功；本区间未执行
  `enable/inspect/disable`，未手工运行 definition，也未重发任何未知结果。
- 相同 5 项 AM/AL 专项与相邻回归再次通过：5 passed、7 条既有 warning。浏览器仍显示“暂无可见工作台入口”，
  门禁保持 NOT GREEN，未触发“重新读取目录”。

## 15:56–16:07Z 持续观察与 Store 前边界诊断

- 第五段监视器观察 AM revision392 至 revision394 后按预设长度正常退出；同一任务续建第六段监视器并连续观察至
  revision413。最新 heartbeat `2026-09-18T16:07:02Z`、lease `16:09:02Z`，state=running、completedAt 为空。
- 权威 Run 逐行复核显示 12 个成员仍为 running、`executor_id` 为空、`rows_written=0`、`finished_at` 为空；三个
  `colima-aos-extension` runner 容器均 Up、未重启，但容器内等待服务进程瞬时 CPU/网络/块 I/O 为 0。容器日志驱动不支持
  读取，因此这些状态不能单独证明业务执行推进或失败。
- Store 边界仍为 dataset receipts=12、relationship journal=1、link command=1/linkCount=1168、retirement=0、
  原 idempotency key Store Receipt=0、ecom_link=0、link outbox=0、projection pending=0；resources=3、dev-org canary=0。
  attempt 事件只有 1 条 accepted 与连续 heartbeat，数据库会话无 blocker。未知结果尚未跨 Store 提交边界，禁止重发。
- 首次 Run 逐行查询误用了不存在的 `snapshot_group_id` 列，事务回滚且无写入；随后按正式 member→run 连接键完成复核。
  host PID 99810 持续运行并更新状态文件，未发现本轮新异常终止记录。
- 相同 5 项 AM/AL 专项与相邻回归再次通过：5 passed、7 条既有 warning。浏览器电商目录没有可见性变化，
  门禁保持 NOT GREEN，未触发“重新读取目录”。

## 16:07–16:13Z 对象重放边界与持续观察

- 第六段监视器继续观察 AM revision414 至 revision415 后按预设长度正常退出；同一任务续建第七段监视器并连续观察至
  revision425。最新 heartbeat `2026-09-18T16:13:07Z`、lease `16:15:07Z`，state=running、completedAt 为空。
- Store 对象侧按 stream 复核：P01–P12 均已有原始 `ecom_ingest_receipt`；authoritative Store 对象 outbox 累计
  objects_written=1558、objects_tombstoned=183，二者 pending 均为 0。最新对象 Receipt/投影均早于 AM attempt，说明 AM
  正在复核并重放既有幂等结果，没有制造重复对象写入。
- runtime host 状态文件仍按 2 秒刷新，主循环未被恢复任务阻塞；进程线程与 attempt heartbeat 均保持存活。Store link
  Receipt 仍未出现，因此本轮仍禁止重发、手工 run_definition 或执行终态收口。
- 相同 5 项 AM/AL 专项与相邻回归再次通过：5 passed、7 条既有 warning。浏览器 accessibility tree 无变化，电商目录
  继续保持 NOT GREEN，未触发任何页面动作。

## 16:13–16:29Z Store 投影证据性能修复与持续观察

- AM 只读监视从 revision426 连续推进至 revision457/running；最新 heartbeat `2026-09-18T16:29:17Z`、lease
  `16:31:17Z`，completedAt 为空。期间没有手工运行 definition、重发未知结果或热替换当前 runtime host。
- 根因复核确认 `read_batch_projection_evidence()` 会先经 `read_committed_batch_revision()` 完整复核，再在第二个事务重复复核；
  `_reconcile_base_events()` 又逐实体读取当前记录与 outbox。24 个对象的 Red 测试记录到 98 条相关 SELECT。
- 按独立方案文档完成最小批量化：当前对象、当前关系、关系端点及候选 outbox 各按作用域批量读取，并在同一事务内复核一次、
  计算 revision；Receipt、完整 identity、payload hash、唯一 outbox、墓碑端点和 derived binding 规则不变。
- 对象批次和对象+关系混合批次的查询上界专项测试通过；Store 全文件回归 62 passed（随后新增混合关系覆盖后继续执行全量复验）。
  AM/AL 及 group relationship/link/retirement/completion 相邻回归为 9 passed、24 skipped、7 条既有 warning。
- 浏览器仍稳定加载 AOS v1.6.5，电商目录为“暂无可见工作台入口”；门禁保持 NOT GREEN，未触发“重新读取目录”。

## 16:29–16:42Z 提交后守护与当前授权重验线索

- Store 批量复核实现以 m1 `bc768a24` 提交且未 push；正式 D-waves 与 AOS 接续上下文在 docs/m1
  `e79a4e9` 登记。当前 runtime host 已加载旧代码，未重启、热替换或以新实现干预 AM。
- AM 从 revision458 连续推进至 revision481/running；权威边界在 revision476 时仍为 members=12、running Run=12、
  dataset Receipt=12、relationship=1、link command=1、retirement=0、link Store Receipt=0、`ecom_link`=0、
  link outbox=0、projection pending=0、live resources=3、dev-org canary=0。事件为 1 条 accepted 与 475 条 heartbeat。
- 两次组合只读查询先后误用了 dataset Receipt 的 `group_id` 和 attempt event 的 `kind` 列，事务均回滚且没有写入；
  通过 information_schema 确认正式列后，第三次只读查询成功。该过程未触发业务执行或未知结果重发。
- `pg_stat_activity` 显示主恢复会话自 16:28Z 保持同一事务，最后查询时间在 16:39Z、16:41Z 持续更新；三个
  runner 容器均 Up，恢复 PostgreSQL 瞬时 CPU 约 25%。现场反复查询为当前安装 composition/lock 核验，说明 AM
  正在慢速重验而非停死，Store 逐实体复核不是唯一潜在耗时段。两条长期 advisory-lock 会话无 blocker 证据。
- Prime Agent 两个进程存活；00:31 本地健康快照为 `GREEN_WITH_WARNINGS`，7 个强一致投影 CURRENT、1 个异步投影
  PENDING_ASYNC。其 delivery status 仍为较早 AR2 门禁，只作为开发记忆辅助，不作为 AM 当前事实权威。
- 浏览器既有页面仍为 AOS v1.6.5 且电商目录“暂无可见工作台入口”，门禁 NOT GREEN。下一波方案先行评估同一
  恢复事务内已加锁当前安装权限的安全复用，保留跨事务、跨连接、跨租户和回调后非权限事实的完整重验。

## 16:42–17:03Z 恢复事务权限复用实现与持续守护

- AM 只读监视从 revision482 连续推进至 revision523/running；最新 heartbeat `2026-09-18T17:02:44Z`、lease
  `17:04:44Z`，completedAt 为空。runtime host PID 99810 与 `caffeinate` PID 9489 均存活；未手工运行 definition、
  未重发未知结果、未重启或热替换当前 host。
- 方案先行实现当前安装权限的事务内 exact 复用：首次完整检查仍取得原安装/成员资格/标记/组合证据锁，只有严格 `True`
  才缓存；作用域退出或异常立即 reset。Receipt、definition、saved facts、十二 bindings、schedule/control、policy 与回调后
  `_load()` 比较仍逐层重读。
- Red 记录嵌套恢复进入完整控制权限 8 次；Green 降为 1 次，第二个顶层事务重新检查。recovery authority 7 passed，
  相邻恢复链 23 passed，配置/生产入口 3 passed，静态编译和差异检查通过。并行测试库角色争用与原测试 DSN 丢密码问题
  均在串行及隔离连接工厂下消除，不属于产品运行失败。
- 浏览器只读复验稳定加载 AOS v1.6.5，但电商目录仍为“暂无可见工作台入口”；没有点击“重新读取目录”，浏览器门禁
  保持 NOT GREEN。测试绿与页面存活均未被当作 AM 或真实经营闭环成功证明。

## 17:03–17:19Z 提交后边界复核与进程采样

- 权限复用改动以 m1 `f5de30e4` 提交且未 push；只精确提交恢复入口的一行接线，未夹带该文件既有未提交改动。当前
  runtime host 仍为提交前进程，未重启、热替换或宣称已使用新实现。
- AM 从 revision524 连续推进至 revision555/running。revision548 的权威复核保持 members=12、running Run=12、
  dataset Receipt=12、relationship=1、link command=1/linkCount=1168、retirement=0、原 key link Store Receipt=0、
  `ecom_link`=0、link outbox=0、projection pending=0、live resources=3、dev-org canary=0；未知 Store 结果未越界。
- 瞬时 `pg_stat_activity` 未见长期事务，三个 runner 容器仍 Up 5 小时且服务进程等待。host PID 99810 瞬时约 9.4% CPU；
  三秒只读采样显示主线程多数时间在事件循环等待、三个容器管理线程在 `waitpid`，活跃片段主要为周期任务建立 PostgreSQL
  连接时的 SCRAM 认证。该采样只能解释部分 host CPU，不能证明 AM 业务步骤推进、停滞或失败。
- `pg_stat_statements` 未启用，未伪造累计 SQL 归因。AM 固定收口脚本离线专项 4 passed；浏览器沿上一轮只读结果保持
  AOS v1.6.5 与“暂无可见工作台入口”，门禁仍 NOT GREEN。本区间未运行 definition、未重发、未改变治理或运行态。

## 17:19–17:24Z 独立控制窗口核对与失败预案

- AM 从 revision556 连续推进至 revision565/running；heartbeat 与两分钟 Lease 持续更新。首次窗口查询误用了 member 表不存在的
  `control_ref` 列，事务回滚且无写入；随后按 information_schema 与正式 payload 结构完成只读核对。
- 十二个 AM 当前控制均为 revision2，有效窗 `2026-09-18T12:38:10.986989Z` 至 `18:38:10.986989Z`；本次成功读取时
  距截止约 1 小时 16 分。budget policy rev8 有效至 `2026-09-19T11:48:51.753918Z`。attempt heartbeat 不能延长控制窗，
  因此不以 Lease 健康替代业务时效判断。
- 仓库尚无 AN 后继脚本。新增 `am-expiry-failure-contingency-plan-20260919.md`，只定义 failed 后的 Store unknown 边界、
  AM 正式退休与 direct successor AN 文件级施工清单；当前 running 明确禁入，未创建 AN、未续签、未禁用、未重发。
- 若 AM 先 succeeded，失败预案立即失效并执行既有 enable/inspect/disable；若 failed，必须先固定 terminal event 和原 key
  Store Receipt，再按方案测试先行实施。浏览器门禁继续 NOT GREEN，230 L0 继续挂起。

## 17:24–17:29Z 确定性只读 guard

- AM 监视继续到 revision574/running。为替代易受 schema 漂移影响的临时 SQL，方案先行新增
  `scripts/a0v_am_attempt_guard.py`：只读取 exact identity、definition/recovery、12 Run、Store/投影、资源、canary 与控制窗口，
  仅输出 `RUNNING_NO_ACTION`、`SUCCEEDED_RUN_CLOSURE` 或 `FAILED_DIAGNOSE_BOUNDARY`，不自动执行动作。
- Red 为脚本缺失；Green 专项 11 passed，相邻 AM saved recovery 合计 12 passed，静态编译与差异检查通过。真实运行输出
  revision574、`automaticAction=false`，权威边界与人工核对一致，控制剩余 4147 秒。
- guard 运行前后没有业务状态写入；自然 heartbeat 可继续推进 revision。该工具不替代 Store Receipt 对账、终态收口、浏览器
  门禁或真实经营闭环验收。

## 17:29–17:37Z 运行角色可见性纠正与 AM 无锁等待诊断

- guard 继续读到 revision582/running，heartbeat `2026-09-18T17:32:39Z`、lease `17:34:39Z`，控制窗口
  剩余 3921 秒；12 Run、12 dataset Receipt、1 relationship、1 link command/linkCount=1168 均不变，
  link Store Receipt、`ecom_link`、link outbox、retirement 仍为 0，未发生未知结果重发。
- 前一次 20 秒 `pg_stat_activity` 采样使用的是限权 runtime 角色；该角色对其他后端的
  state/query 只能看到 `NULL/<insufficient privilege>`。因此“未见活动 SQL”的原判断无效，
  不再用作 AM 进度或停滞证据。
- 改用恢复库容器内 owner 的 `BEGIN READ ONLY` 视角后，确认 AM 主恢复会话处于同一个持续事务中；
  当时事务已运行约 12 分钟，持有 162 个已授予锁、0 个等待锁，`pg_blocking_pids` 为空。
  15 秒/0.05 秒高频只读观察中，该会话持续轮询 composition lock（180/302 个有效样本），
  并穿插读取当前 pipeline graph、ingress command、budget/model/runtime/guard policy 及 installation 锁。
- 因此当前更精确的判断是：AM 没有被 PostgreSQL blocker 卡住，而是在旧 host 进程中慢速重复完整当前
  权限/composition 验证。m1 `f5de30e4` 已将同事务的该类完整权限检查从 8 次降为 1 次，
  但 AM 仍是旧进程；为保护 unknown Store 边界，本段未重启、热替换、终止或重发。
- 修正诊断后 AM/AL 收口专项 12 passed，7 条既有 warning，`diff --check` 通过。浏览器只读树确认
  AOS v1.6.5 正常加载，但电商工作台仍显示“暂无可见工作台入口”；未点击“重新读取目录”，
  因此浏览器门禁仍为 NOT GREEN，不以页面存活替代真实首链完成。

## 17:39–17:42Z attempt 累计时长只读观测

- 在原 guard 方案内先补充观测扩展，再用 4 个 Red 用例证明既有分类器不校验累计时长和
  窗口过期一致性。最小修改仅在同一 SELECT-only 事务内读取 `accepted_at`，输出累计秒数、
  控制剩余秒数和过期标志；过期 running 仍只返回 `RUNNING_NO_ACTION`。
- 实现后专项与 AM 收口相邻回归 17 passed，7 条既有 warning，静态编译和差异检查通过。
  真实 guard 读到 AM acceptedAt `2026-09-18T12:38:52.369786Z`、elapsed=18208s、
  revision601/running，控制剩余 3350s、expired=false；原 Store/Run/resource/canary 边界不变，
  `automaticAction=false`。
