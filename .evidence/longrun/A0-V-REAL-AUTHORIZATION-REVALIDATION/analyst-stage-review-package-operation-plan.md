# 经营参谋阶段评审包侧 operation 方案

日期：2026-09-12

基线：`64208eb7`

状态：实施完成，宿主 IPC 适配与 1.5.0 Candidate 待办

## 目标与边界

在作者树既有 `ecommerce_growth_review_advance` operation 下开放四种严格、无副作用消息：
`validate_command_identity`、`validate_review_slot`、`validate_runtime`、`validate_eval_proof`。
每种消息键集合必须完全匹配，并复用 9.13—9.16 包内纯规则；只返回最小确认引用。

该协议不读取 TenantScope/数据库，不认证 Principal，不判断 current/latest，不写 Receipt/决定，
不调用 Provider。宿主后续只能经安装 runtime IPC 调用，禁止直接 import 作者树。当前 canonical
1.4.0 与 Installation 不变；待清册边界闭合后统一构建 1.5.0 Candidate。

## 文件

- 修改 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py`。
- 新增 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analyst_stage_review_runtime_operation.py`。
- 新增 `services/aos-api/tests/extension_runtime/test_analyst_stage_review_runtime_operation.py`。
- 更新 closure manifest，并新增本波 files/verification 证据。

## 退出与下一门

四消息正例、严格 envelope、未知消息/operation、既有 derive operation 回归、隔离 import、编译与
AR2-7 closure 全绿后提交。下一波实现宿主经已安装 runtime 调用的窄适配，不直接 import 包；
第 9 节整体与 1.5.0 安装仍 PENDING。
