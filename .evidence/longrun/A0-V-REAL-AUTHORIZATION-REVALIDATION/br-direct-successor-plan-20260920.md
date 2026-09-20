# BQ released-owner 正式退休与 BR direct successor 方案（2026-09-20）

## 1. 当前权威

- HEAD `c945bdbf`。BQ installation `4faaf3b7-2d10-4961-99db-5bf52b7b8a63` /
  generation `b53ce5ac-169c-4d69-9780-58beb8ad736c` active etag5；唯一 binding
  rev7/epoch4 为 disabled/fenced、desired enabled、observed unknown，三资源均 released。
- 九路仍指向 BQ extension rev174/group201；definition rev124 disabled，BQ attempt=0；12 members、
  12 个仍 running 的保存 Run与12 Dataset Receipt保持。本快照组 link Store Receipt=0、
  `ecom_link=0`、projection pending=0、canary=0。
- BQ 保存恢复波已在 transfer 写入口前安全停止；禁止复活该 released generation、禁止重试 transfer、
  禁止读取商城源数据或调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定上述 BQ released-owner、路由、definition、attempt=0、12 Run/Receipt、
   零副作用与 m1 单写者边界；Runtime Host=0、18181=0。
2. **正式退休**：复用正式 released-owner settlement，严格执行
   `preflight -> request-disable -> process-disable -> audit`。目标 binding rev9/epoch5
   disabled/fenced/desired disabled，九路 legacy rev176/group203，三资源 released；fence/detach
   Receipt各一。unknown operation只读对账，不换键、不重发。
3. **创建 BR**：只接受 BQ exact detach Receipt为 predecessor，使用当前 canonical `.2` 四 bundle
   创建全新 installation/generation；启动唯一 Runtime Host后串行 prepare/verify/stage/configure/enable，
   第二 Host=0。
4. **注册与切换**：以 BQ detach Receipt注册 BR successor；串行 approve、prepare、pause、commit、
   validate、resume，目标九路 extension rev177/group204。
5. **健康观察**：definition rev124持续 disabled；至少12次新增 lease renewal，BR attempt=0，12
   Run/Receipt与本波业务副作用保持0，canary=0。Host failure或代际释放立即停止，不宣称 GREEN。
6. **verification/commit**：最终只读 observe、专项与共享测试、verification、精确提交；若 BR 仍为
   enabled/ready/live，下一波进入 BR saved-snapshot recovery；否则冻结实际边界并直接进入 BR 正式退休与
   BS direct successor。

## 3. 停止条件

- BQ identity、binding rev7/epoch4、route rev174/group201、definition rev124、三资源 released、
  attempt=0、Run/Receipt或零副作用边界漂移；
- retirement/create/lifecycle/register/cutover出现 unknown 或部分提交；第二 Host、worker或 attempt；
- 手工 `run_definition`、BQ transfer重试、商城源读取、负租户写入或直接 SQL 改写运行权威。

全程不 push、不动其他分支，230 L0继续挂起。非人工决策型工程阻断在上述边界内自行诊断、补证据、
最小修复并继续。

## 4. 现场增补：配置治理 authority 到期

BR prepare/verify 已正式 succeeded；首次 stage 在任何 configuration 写入和 stage 结果文件形成前，被
`budget policy is not effective` 拒绝。BR 当前仅为 binding rev1/epoch1 disabled/fenced/ready，三资源
pending，唯一 Host仍健康；该拒绝不是 unknown operation，不允许绕过策略或直接改表。

恢复插入以下既有正式子流程：

1. 新建 BR 专属私有 journal，使用已评审 `text-readiness-v2` 三个公共合成文本案例；先做零调用
   preflight，每例最多一次 Provider 调用，任一失败/未知保留 intent且停止，不读取商城或客户输入。
2. 三例通过后，用 `a0v_formal_text_model_renewal.py` 在新 state/evidence 目录冻结续期计划，再以同一
   planHash经 Budget/Policy/Model/Route Owner和原 CAS/EvalGate apply；apply阶段 ProviderCalls=0、
   businessRuns=0，未知提交只读查回，不创建新计划覆盖。
3. 续期后重新执行尚未写入的 BR stage；其 configuration 自动引用 current exact authority。随后继续
   configure/enable和原步骤4–6。若现有 Host 因等待期间释放 BR generation，则停止本波并转正式退休，
   绝不原地复活。
