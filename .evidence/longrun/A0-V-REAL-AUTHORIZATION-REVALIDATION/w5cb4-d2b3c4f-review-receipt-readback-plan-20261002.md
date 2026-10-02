# d2b3c4f 原 Review Receipt 读回合同：文件级计划

## 上位方案与进入事实

复习 `231-工作台业务闭环长程开发路径与波次实施计划` 的 A1 首链、`231-9-栖月汇双侧增长技术合同与原计划增量清单` 的原阶段人工决定→Handoff→内部内容 Task，以及 D-waves `2026-10-01-W5CB4-BG00gw原Review来源合同清单` 的 d2b3c4f 余项。当前 `ReviewAdvanceHostService` 对 `accepted-stage-v1` 的 `revalidate` 和 `execute` 均失败关闭，`verify_receipt` 无条件返回空；现有单元夹具不是原始生产者，当前真库 Review Receipt/Host binding 为零。正式 E17 身份、八类配置和 Growth1.13 发布另门。

## 本切片范围与精确文件

- `services/aos-api/tests/extension_runtime/test_ecommerce_review_advance_host.py`：先 RED，给已持久读回的新来源 Receipt 一个同租户、同 idempotency key、同原命令 17 项 lineage、请求哈希与回执自哈希的正反合同；错租户、错 key、错 lineage、篡改回执均拒。测试替身仅验证读回函数，不宣称原生产者或当前实例通过。
- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：只改 `ReviewAdvanceHostService.verify_receipt` 的新来源分支；从现有 `_HostReviewReceiptStore` 按当前 scope/key 读回，严格校验持久回执与命令并保持旧分支不变。`revalidate`、`execute`、Provider、Host 启动均不改。
- 本计划与 verification/D-waves/01/06：记录 RED、专项与相邻回归、浏览器禁入及尚未解决的原生产者缺口。

## 安全和退出判据

原 Review producer 的 Stage TaskRun/Plan/Attempt/Eval/Artifact/permission、AnalysisRuntimeReceipt、当前 Case/Occurrence 和同代 binding 仍需独立原生产者联合验证；本切片不能解除 `accepted stage Handoff Owner is not wired`。当前真实库只读，PG 写测试只在 `aos_test_*_ti4_test` 可销毁库。回滚为精确撤销本切片两文件提交；不触当前安装、旧 12 Run、商城源、230 L0、外部动作或 push。
