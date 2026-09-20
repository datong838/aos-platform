# BT 保存快照恢复与单一自然 attempt 方案（2026-09-20）

## 1. 当前权威

- HEAD `3e1d38bf`；BT installation `b05b7f06-67a0-4ea1-bc7c-1ba2108653d5` /
  generation `2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58`，binding rev6/epoch3 enabled/ready，
  九路 rev183/group210，attempt=0；唯一外置 Runtime Host PID 4492。
- definition rev127 disabled/hash
  `sha256:4e373626f25a3fcb643e04f5cf3468b553c5c03815c347098840a18c15697aa0`；recovery
  rev41/hash `sha256:400cf5d221f28501d763b194fb412a18a2c23c872057fe6e5f4c896a7721935d`。
- 12 members、12个仍running的保存Run、12 Dataset Receipt；本快照组 Store Receipt=0、
  `ecom_link=0`、projection pending=0、canary=0。当前恢复窗有效至
  `2026-09-20T18:24:03.288076Z`。
- 本波只转移既有冻结输入，不读取商城源数据，不调用 `run_definition`。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定上述BT、definition/recovery、attempt=0、零副作用与单Host边界。
2. **纯HTTP 18181与唯一Host**：重启恢复时曾正常停止唯一外置Host并读回Host=0、18181=0、
   snapshot worker=0；该动作按正式Host stop协议把BT推进为rev7/epoch4 disabled/fenced。不得伪造旧
   rev6/epoch3；通过唯一外置Host自然恢复当前generation并读回新的ready binding，再与受控纯HTTP
   API并存。API必须读回Cron=false、snapshot worker=false、进程内Host=false，且外置Host总数恰好1、
   第二Host=0。
3. **冻结输入转移**：HTTP prepare/schedule-ingest/controls后，从BT前驱rev127/recovery41执行
   transfer -> BT rev128 disabled、renew -> recovery42/definition rev129 enabled，全部读回
   `sourceReads=0`；preview必须绑定Host恢复后的精确binding revision/epoch，不放宽其他授权；关闭
   纯HTTP并确认18181释放。
4. **唯一自然worker**：创建BT专用attempt guard、worker与supervisor；启动前证明Host=0、worker=0、
   attempt=0，禁止手工 `run_definition`、第二worker/Host/attempt。
5. **连续观察**：supervisor以50秒只读采样至唯一attempt正式terminal；若300秒仅因
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`终结且12 Run与零副作用不变，则按原accepted_at在
   1800秒预算内走正式有界延续路径，不在BT内手工重发。
6. **终态/verification/commit**：正式终态后stop-only推进definition rev130 disabled；落
   verification、测试、精确提交；自动进入BT正式退休与BU direct successor。

## 3. 停止条件

任一identity/Receipt/hash/revision/Run/route漂移，出现第二Host/worker/attempt、商城源读取、负租户写、
业务副作用、未知提交边界、配置治理过期或手工执行时立即fail closed；未知结果不得重发或换幂等键。
不push、不动其他分支，230 L0继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
