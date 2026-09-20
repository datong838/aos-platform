# BU 正式退休与 BV direct successor 方案（2026-09-20）

## 1. 当前权威

- HEAD `1681695a`；BU installation `d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895` / generation
  `cb8ace71-ba8d-4e08-816b-8d6bbc0f0281`，binding rev6/epoch3 enabled/ready，九路
  rev186/group213，三项live resource，唯一外置Runtime Host PID 10997。
- 唯一attempt `617da078-f4ef-4ad9-9ac6-bd764468fa67`已正式failed rev4，原因
  `RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev130 disabled，recovery42，
  自然worker已停止。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link=0`、projection
  pending=0、canary=0。不读取商城源数据，不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：冻结上述exact authority；核对m1单写者、唯一Host、worker=0、18181=0。
2. **BU Host释放与正式退休**：精确终止PID 10997，读回released-owner rev7/epoch4与三资源released；
   以唯一failed attempt、definition rev130、九路rev186/group213执行正式disable settlement，目标binding
   rev9/epoch5、legacy rev188/group215，并取得唯一fence/detach Receipt。
3. **BV创建与lifecycle**：仅以BU detach Receipt为predecessor创建新installation/generation；串行
   prepare、verify、stage、configure、enable；prepare accepted后只启动唯一外置Host自然领取。
4. **注册与九路cutover**：唯一幂等键注册BV；串行approve、prepare、pause、commit、validate、resume，
   目标九路rev189/group216，禁止重复切换。
5. **唯一Host与健康观察**：第二Host=0、18181=0、snapshot worker=0；只读repeatable-read观察
   lease renewal、binding ready、route一致与attempt=0。
6. **verification/commit**：读回12/12与全部零副作用，落verification、测试、精确提交；自动进入BV
   saved-snapshot recovery。

## 3. 停止条件

任一identity/Receipt/hash/revision/attempt/Run/route漂移，Host停止后资源非released，出现第二Host/worker、
商城源读取、负租户写、业务副作用、未知提交边界或手工执行时立即fail closed。未知结果不得重发或更换
幂等键；不push、不动其他分支，230 L0继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
