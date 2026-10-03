# s3o-w-ae BI 私有有限分发验证（2026-10-03）

## 依据、变更与 RED

- 依据：231-9、栖月汇产品方案、D-wave s3o-w-ae、同波文件级 plan。现有进程只有 listener 准入，IPC、OIDC、attempt marker、原 Plan 服务和 Receipt Reader 已有实现。
- RED：`pytest -q services/aos-api/tests/aip/test_aip_bi_plan_issuer_process.py -k finite_process`，退出 1，`AttributeError: module ... has no attribute run_bi_issuer_process`。
- 最小改动：`aip_bi_plan_issuer_process.py` 从本地可信签名根、source alias 和单一独立 BI DB 身份组装原 resolver、prepare/rebind 服务与原 Reader；有限 accept 复用现有私有 IPC、kernel peer、OIDC、租户及持久 attempt 门。客户端不提供 DB、签名根或 actor。

## 验证输出

| 验证 | 输出 | 退出码 |
| --- | --- | --- |
| 进程专项 `pytest -q services/aos-api/tests/aip/test_aip_bi_plan_issuer_process.py` | 16 passed | 0 |
| Growth 1.13 签名 full-schema 隔离库 | 1 passed，7 warnings，11.83s | 0 |
| Growth 1.12 签名隔离克隆相邻链 | 1 passed | 0 |
| BI 进程/IPC/服务/连接/鉴权/Resolver/原服务相邻回归 | 116 passed | 0 |
| `python -m py_compile`（改动 Python 文件）、`git diff --check` | 无错误 | 0 |

Growth 1.13 测试在可销毁签名 full-schema 库中调用**原** `SignedBIPlanActiveRebindService.rebind` 提交真实 Plan/Receipt 后注入回执丢失。第一次分发从原只读 Reader 得 `observed`，同键第二次只读得相同结果且原服务不得重发；同键改命令 `conflict`，缺 prepare Receipt 两次 `unresolved` 且不重发；`dev-org` 在分发前拒绝。两条持久 marker 不含测试 bearer token。测试专用 OIDC Principal 是隔离验证替身，不能解释成正式身份通过。

隔离测试后只读当前库：`aos_current_preview_20260927@a0v_135`；测试 BI 角色数 0，残余 `aos_test_*_ti4_test` 数据库数 0，当前 Plan 数 0。未对当前库写入、未启动 Host/worker/Provider、未发业务 Run。

## 方案一致性与边界

实现遵守计划的同一独立 DB 工厂、原 resolver/service/Reader、有限 accept 和未知提交只读对账。进程 accept 的单元测试为合成连接，**真实不同 OS UID 的正向 socket 连接尚未证明**；正式 IdP、角色与租户映射、六 Agent、当前库迁移及 Growth 正式激活均是独立门。当前 API/页面保持失败封闭，不能据此宣布首链、发布或生产准入。下一切片先解决实际不同 UID 的私有 socket 和正式身份候选，再做当前实例的安全迁移评估。
