# SC4-5l6i 当前 D P02 首批次失败诊断

日期：2026-09-15  
基线：`9ef1fd4a`  
租户：`org-org/dev-project`；负租户：`dev-org/dev-project`  
安装：`e39ed226-97e7-4271-b1e0-fb485f7e90a6@5`；generation：`04e71cc0-fff3-48bd-b357-1518ddd504a4`

## 真实运行事实

- Schedule：`sch-p02-qyh-controlled-20260913-v1`，执行前临时 enable，运行结束后已 disable。
- Run：`scr-f22003e66e544ebe`，`failed`、`executor_stopped=true`、`PIPELINE_EXECUTOR_FAILED`。
- Source claim 的调用序号为 1；真实源读取完成并将 65 条完整商品规范命令保存到 `ecommerce_ingress_command`。
- 原 Run 阶段计数：command=1、derived=0、dataset=0、recoveryClaim=0；没有 Dataset 完成事实。
- canary 的 controlled source claim 为 0；没有上游写、外部发布、触达、价格、投流或履约副作用。

## 精确根因

对保存命令和当前权威 Product 逐对象、逐 payload hash 只读核对：

- 65 个身份全部存在；
- 64 个完整 payload 相同；
- `niushop:1:32` 的 `stock` 与 `saleNum` 变化；
- 该行传入和已存的 `source_updated_at` 完全相同，均为 `2026-05-31T00:11:49Z`。

P02 当前 Niushop 1.22 mapping 使用 `aos.snapshot-materialization/v2`，把 `modify_time`（零值回退 `create_time`）声明为权威版本时间；实际源表的库存/销量变化未同步推进该字段。因此：

1. 新命令沿用旧的“pipeline + 最大源游标”幂等键；
2. 同 key 的历史 Receipt 请求 hash 为 `bda94a60...`，本批命令 hash 为 `af3527ef...`；
3. `EcomConsistencyStore.read_committed_batch` 精确返回 `IDEMPOTENCY_CONFLICT`；
4. 即使绕过撞键，行 32 仍应被“同版本不同载荷”军规拒绝。

SSH、JDBC、真实 302 表访问、65 行读取和规范化均非本次根因。通用错误边界没有泄露业务载荷，但控制器旧 outcome `CURRENT_PRODUCT_SNAPSHOT_EXECUTED` 容易被误读成成功，已修正。

## 裁决与修复路由

原 Run 的命令不可变且本身与历史 Receipt 冲突，不具备 exact saved recovery 条件，永久保留 failed；禁止改 Journal、旧 Receipt、checkpoint 或放宽同版本约束。

采用仓库已有 `aos.snapshot-materialization/v3`：

- P02 改为 `time_basis=observation`；
- 明确输出 `sourceUpdatedAtBasis=observation` 与 `sourceModificationTimeKnown=false`；
- 完整观测时间成为诚实版本，源表业务时间不再冒充可靠修改水位；
- `EcomConsistencyStore` 的同版本差异、租户、Receipt、checkpoint 和投影约束不变。

签名资产不可就地改。下一波生成 Niushop 1.23 候选并执行签名、D→E 正式重装；E 获得新的 SourceSelection/RuntimeControl/ScheduleBinding 后，才允许一个新 Run 再做一次源读。

## 代码与验证

修改：

- `scripts/a0v_qyh_current_product_event_first_chain.py`
- `services/aos-api/tests/extension_runtime/test_a0v_qyh_current_product_event_first_chain.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6i-qyh-current-product-event-first-chain-plan.md`

控制器现在只在 Run `succeeded` 时输出 `CURRENT_PRODUCT_SNAPSHOT_SUCCEEDED`，已知 failed 输出 `CURRENT_PRODUCT_SNAPSHOT_FAILED`；observe 增加 command/derived/dataset/recoveryClaim 计数。

验证：

```
AOS_TEST_USE_SHARED_DATABASE=1 ... pytest   test_a0v_qyh_current_product_event_first_chain.py   test_pipeline_snapshot_materialization_v2.py   test_pipeline_snapshot_materialization_v3.py
95 passed
```

首次未带共享库开关的运行在夹具连接 `127.0.0.1:5433` 前置阶段失败；没有进入测试逻辑。按本任务既定共享库方式重跑为 95/95 通过。进程退出时仍有既存 JDBC cleanup logger 对已关闭 capture stream 的非功能警告。

## 结论

`CURRENT_D_P02_SOURCE_VERSION_CONTRACT_BLOCKED`

第 4/6 步没有冒充通过。真实源读取与持久化输入已证明，当前阻断为签名包中的 P02 时间语义不符合真实源行为。下一波任务：Niushop 1.23 P02 observation-version 包修复、签名、D→E 重装和新鲜批次复验。
