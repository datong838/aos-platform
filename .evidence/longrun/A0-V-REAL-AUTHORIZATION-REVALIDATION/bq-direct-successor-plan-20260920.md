# BP 单失败终态退休与 BQ direct successor 方案（2026-09-20）

## 1. 当前权威

- HEAD `8675380c`。BP installation `17ba9792-9f24-42e4-9557-4d84547c7d97` /
  generation `4f1bddfa-74a0-4fcb-b25e-f363139eed83` active etag5；binding rev6/epoch3
  enabled/ready/unfenced，三资源live，九路extension rev171/group198。
- definition rev124 disabled。唯一attempt `051397ad-7027-4ee5-9d4c-f32374841cd9`为rev5
  `failed / RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。
- 十二Run仍running、十二Dataset Receipt保留；Store Receipt、`ecom_link`、outbox、projection pending、
  retirement与canary均为0。snapshot worker=0、supervisor=0；唯一外置Runtime Host PID 57278仍运行。
- 禁止在BP内再次执行；当前正式动作只能是退休及从exact detach authority创建直系BQ后继。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定上述BP、唯一正式失败attempt、definition rev124、route/binding、十二
   Run/Receipt、零副作用与单写者边界。
2. **正式退休**：核对PID、命令、status-file与唯一Host后SIGTERM；预期原Host Owner先形成released-owner
   中间态，再复用正式settlement `preflight → request-disable → process-disable → audit`。目标binding
   rev9/epoch5 disabled/fenced/desired disabled，九路legacy rev173/group200，三资源released，fence/detach
   Receipt各一。未知operation只读对账，不换键、不重发。
3. **创建BQ**：只接受BP exact detach Receipt作为predecessor，用当前canonical `.2`四bundle创建新
   installation；启动一个Runtime Host，串行prepare/verify/stage/configure/enable，第二Host=0。
4. **注册与切换**：以BP detach Receipt注册BQ successor；approve → prepare → pause → commit → validate
   → resume，目标九路extension rev174/group201。
5. **健康观察**：definition rev124继续disabled；至少12次新增lease renewal，BQ attempt=0、十二
   Run/Receipt与所有业务副作用=0、canary=0。
6. **verification/commit**：最终只读observe、专项与共享测试、verification、精确提交；随后自动进入
   BQ saved-snapshot recovery。该后续波只能产生一个自然attempt，worker对首个unknown tick立即停止。

## 3. 停止条件

- BP attempt、definition、route/binding、资源、Receipt/hash或业务零副作用边界漂移；
- Host PID/命令不精确、SIGTERM后未按有界规则停止、第二Host或第二worker；
- disable/create/lifecycle/register/cutover出现unknown或部分提交；
- 手工`run_definition`、商城源读取、负租户写入、重跑BP或直接SQL改写运行权威。

全程不push、不动其他分支，230 L0继续挂起。所有非人工决策型工程阻断在上述边界内自行诊断、补方案、
最小修复和继续。
