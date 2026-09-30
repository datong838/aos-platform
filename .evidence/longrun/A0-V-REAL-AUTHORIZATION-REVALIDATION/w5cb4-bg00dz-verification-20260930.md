# W5CB4 BG00dz｜签名 BI Plan 原安装 Receipt 绑定存储验证

## 方案与变更

按 `w5cb4-bg00dz-unknown-result-plan-20260930.md`，仅对新的 `bi_responsibility_plan.prepare` Receipt 在原 Plan ref 顶层增存 `installationBinding`：原安装 UUID、强 ETag 版本、精确模板 ref、原 actor。写前验证四字段和模板与 Plan 请求一致。Plan 与 Receipt 原同事务、幂等哈希及通用重放合同不变；旧 Receipt 无绑定时继续可只读读取。BG00dy 的 GET 对新旧 Receipt 都仍返回 `installationBindingVerified=false`，避免 API/SDK 在未联合升级前声称绑定已证明。

| 检查 | 命令与结果 |
| --- | --- |
| RED | 隔离 PG `pytest -k later_failure_rolls_back_draft_receipt` → exit 1，`KeyError: installationBinding`。 |
| 聚焦 | `pytest -k 'later_failure_rolls_back_draft_receipt or signed_bi_receipt_readback'` → exit 0，5 passed。 |
| 相邻累计 | BI authority/readiness/composition、签名模板、W2A/W2B Store/API 七文件 pytest → exit 0，102 passed。 |
| 静态 | `py_compile`、`git diff --check` → exit 0。 |
| 事务回滚 | 隔离 PG 故意抛出后，Receipt 与 Plan 均 0；同键重放仍只有原 Plan；换安装 ID 同键冲突，见上述隔离测试。 |

## 风险与下一门

JSONB 新字段是未来新 Receipt 的原命令来源证据，不是当前安装/权限/运行准入。旧 Receipt 没有可读原安装绑定，不能回填或猜测；404/网络未知也不授权重发。前端/GET 联合读回新绑定需下一波精确合同、RED 与兼容验证。当前真实库未写，Host/worker/Provider 未启；正式 OIDC、签名安装、六 active 实例、三身份/Owner/八配置候选仍缺正向，真实首链 pending。browser-pilot 当前不可调用，页面截图未补。
