# AM 双 attempt 失败后的正式暂停验证

## 1. 失败终态

- 首笔 attempt `7d6cc3aa-881d-4aff-ac30-58978d06e85d`：failed revision627，completedAt
  `2026-09-18T17:55:05.142739Z`。
- 第二笔 attempt `38e5c7b9-fa37-4d3f-8f3f-769b995b4db3`：failed revision86，completedAt
  `2026-09-18T18:38:11.427241Z`；最后 heartbeat `18:38:08.100209Z`。
- 第二笔在十二项 control 统一到期 `18:38:10.986989Z` 后约 440ms 终结。attempt 表未保存安全 reason
  code，因此这里只记录时间相关性，不把它冒充已持久化的精确异常原因。
- 两笔 request hash 相同；同 generation 没有其他 attempt。12 Run 仍 running，dataset Receipt=12、
  relationship=1、link command=1/linkCount=1168；retirement、原 link Store Receipt、ecom_link、
  authoritative Store outbox、projection pending 均为 0，dev-org canary=0。

## 2. 暂停实现

- `scripts/a0v_am_saved_snapshot_recovery.py` 增加 exact `pause-failed`；门禁同时固定两笔 attempt id/revision、
  无其他/运行 attempt、rev53 enabled、12 个 expired latest control、冻结输入与 Store 零提交边界。
- 唯一写动作调用正式 snapshot definition transition，幂等 key 为
  `a0v-am-saved-snapshot-pause-failed-v1`；没有调用 `run_definition`，没有读取商城源表。
- 第一次执行因新增 SQL 的 66 个占位符与 68 个参数不符，在只读门禁阶段失败；没有 transition、没有结果文件、
  没有状态变化。修复为 66/66 并加入执行前数量校验后，使用同一 key 重试成功。

## 3. 结果

- definition：rev53 enabled → rev54 disabled，priorRef 精确指向 rev53。
- 两笔 attempt 仍分别为 failed revision627/86，没有第三笔 attempt。
- 私有结果：`am-saved-snapshot-recovery-v1/pause-failed-result.json`，权限 0600。
- 专项测试 1 passed；前置 migration/contract 41 passed，failed recovery/worker 13 passed，续窗身份主证
  2 passed，相邻 attempt/Lease 11 passed、3 skipped；静态编译与差异检查通过。
- 暂停后累计脚本/guard 回归 18 passed；浏览器只读复验仍显示 AOS v1.6.5 与“暂无可见工作台入口”，
  未点击重读，门禁继续 NOT GREEN。

## 4. 下一步

AM 已进入可退休空窗。下一波只允许 exact `inspect → request-disable → process-disable → audit`，先确认 Store
Receipt 仍为 0 和三资源/九路 route 当前事实，再通过正式 disable Owner fence、drain、detach；不得直接更新业务表或
创建 direct successor。
