# BO 双失败终态退休与 BP direct successor 方案（2026-09-20）

## 1. 当前权威

- HEAD `a03acc2c`。BO installation `307399a0-21bb-4d55-95b2-8b0fee238913` /
  generation `030bf59c-c998-4ee6-aedb-11d8d7d5831a` active rev5/etag5；binding rev6/epoch3
  enabled/ready/unfenced，三资源live，九路 extension rev168/group195。
- definition rev121 disabled。两个且仅两个 attempt
  `57881020-86fe-44cc-be3e-2cd90787205e`、`9d1fc481-7eb2-426f-8b0b-65627f06ec97`
  均为 rev2 `failed / RECOVERABLE_EXECUTION_EXCEPTION / RuntimeConflict`，request hash相同。
- 十二 Run仍running、十二 Dataset Receipt保留；Store Receipt、`ecom_link`、outbox、projection pending、
  retirement与canary均为0。snapshot worker=0、supervisor=0；唯一外置 Runtime Host PID 99908仍运行。
- 已提交的 alias/source-claim与 worker one-shot fail-closed修复只供 successor使用；禁止在 BO内再次执行。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定上述 BO、两个正式失败 attempt、definition rev121、route/binding、十二
   Run/Receipt、零副作用与单写者边界。
2. **正式退休**：先核对 PID、命令、status-file与唯一 Host，再SIGTERM停止该 Host；复用正式 failed
   retirement `preflight → request-disable → process-disable → audit` Owner路径。预期 binding
   rev8/epoch4 disabled/fenced/desired disabled，九路 legacy rev170/group197，三资源released，fence/detach
   Receipt各一。未知operation只读对账，不换键、不重发。
3. **创建 BP**：只接受 BO exact detach Receipt作为 predecessor，用当前 canonical `.2` 四 bundle创建
   新 installation；启动一个 Runtime Host，串行 prepare/verify/stage/configure/enable，第二 Host=0。
4. **注册与切换**：以 BO detach Receipt注册 BP successor；approve → prepare → pause → commit → validate
   → resume，目标九路 extension rev171/group198。
5. **健康观察**：definition rev121继续disabled；至少12次新增 lease renewal，BP attempt=0、十二
   Run/Receipt与所有业务副作用=0、canary=0。
6. **verification/commit**：最终只读 observe、专项与共享测试、verification、精确提交；随后自动进入
   BP saved-snapshot recovery。该后续波只能产生一个自然 attempt，worker对首个unknown tick立即停止。

## 3. 停止条件

- BO attempt、definition、route/binding、资源、Receipt/hash或业务零副作用边界漂移；
- Host PID/命令不精确、SIGTERM后未按有界规则停止、第二 Host或第二 worker；
- disable/create/lifecycle/register/cutover出现unknown或部分提交；
- 手工 `run_definition`、商城源读取、负租户写入、重跑 BO或直接SQL改写运行权威。

全程不push、不动其他分支，230 L0继续挂起。所有非人工决策型工程阻断在上述边界内自行诊断、补方案、
最小修复和继续。

执行中读回补充：PID 99908收到SIGTERM后2秒内正常退出，并由 Host 原 Owner将 BO推进为 binding
rev7/epoch4 disabled/fenced/desired enabled、三资源released；九路仍为 extension rev168/group195，
两个失败attempt及零副作用边界不变。因此正式退休必须切换到 released-owner settlement，不再使用
active failed-retirement入口。共享 released-retirement只将原硬编码 definition/route revision抽成默认常量，
BO wrapper注入121/168/195/170/197；不改变 Owner、Receipt或数据库写路径。
