# 经营参谋阶段 Eval 报告最小证明方案

日期：2026-09-12

基线：`00d1502a`

状态：实施完成，宿主报告 Owner 与装配待办

## 方案

平台通用 `EvalReportRevision` 连带 Suite、target、dataset、judge、results 等公共合同，不复制到
电商包。growth 仅定义阶段评审所需的最小 `StageEvalReportProof`：tenant、report exact ref、
EvalContract、subject Artifact、StepRunAttempt、GatePolicy、cutoff、gatePassed 和 createdAt。

纯函数核对 report 类型、passed、带时区时刻、cutoff 不晚于 createdAt、createdAt 不晚于宿主
可信 now，以及五项 exact 输入一致。宿主继续独占完整报告/原始行 hash、latest、EvalRun、Suite、
Gate、执行时序、TenantScope 与数据库。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_eval_report.py` | `42738a811ca13568d79b60a73a20af7304bf4f758a43c71930a3b1e49d57d731` | 验证输入；宿主 Owner 不改 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_eval_report.py` | new | 最小证明 DTO 与 exact 比较 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_eval_report_proof.py` | new | 正负合同与隔离 import |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `03fdcaedb52e5181350ba181f4cc358492bc5b719697b2b5bdd2695dd2c0924f` | 登记 9.16 |

## 退出与下一门

DTO schema、合法 exact 输入、报告/时间/五项绑定漂移、布尔版本、隔离 import、相邻回归、编译与
AR2-7 closure 全绿后提交。下一波审计 StageDecision Store 与 command/runtime 的宿主装配方式，
决定是否进入窄端口接线或继续下一纯模块；第 9 节整体仍 PENDING。
