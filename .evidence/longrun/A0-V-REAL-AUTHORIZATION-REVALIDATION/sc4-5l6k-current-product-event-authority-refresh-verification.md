# SC4-5l6k current E ProductEvent authority refresh 验证

日期：2026-09-16  
分支：`m1`；不 push；230 L0 挂起。

## 结论

`A0_V_CURRENT_E_PRODUCT_EVENT_AUTHORITY_REFRESH_GREEN`

当前 E 的九项正式 dispatch 已完成切换并全部为 extension/unfenced；负租户 cutover 写入为 0。真实 Case `case-qyh-full-store-baseline-20260915` 已经经 current E Host 激活到 revision/version 2。切换后的 P02 预检以不可变 CutoverResumeReceipt 证明 runtime binding revision 6，随后正式追加 SourceSelection revision 3、RuntimeControl revision 3、ScheduleControlBinding revision 5。

本标记只证明 Case 与 ProductEvent 上游 authority 已由 current E 接管，不宣称 schedule policy、event control、自然 occurrence 或完整经营首链已经完成。

## 真实读回

- CutoverResumeReceipt：`9389fe3b-162b-4d7c-8c6f-359d34a6fb80`，content hash `sha256:157ce7d71e7d213f02f6933f23e5776c21a31d8b33ba10315c0d2c345d3e0d30`；targetRuntimeRevision=6、claimPaused=false。
- Case：`case-qyh-full-store-baseline-20260915`，ACTIVE，revision/version 2。
- SourceSelection：`source-selection-4bfa23da-510f-482e-92ca-1ec126b3dc5c@3`。
- RuntimeControl：`pipeline-control-3a9f4169-57f4-4fa4-badf-9f2c0d0e035f@3`。
- ScheduleControlBinding：`schedule-control-eeff7221-b61f-4ca5-a6cd-f333947a1cff@5`。
- installation `1c08edfb-ec0d-4abb-a411-7b6ec0d6066a@5`、generation `ebaa620a-8831-4c2a-b971-788383f352f8`、epoch 3、binding revision 6 保持 enabled/ready/unfenced。

## 修复与验证

- P02 预检仍保留安装态 revision 4；revision 6 只有在 frozen result、主库 resume Receipt、Receipt canonical hash、cutover target 与当前 binding 全部精确一致时接受。
- authority refresh 从受租户约束的表读取最新完整行，经既有 decoder 复验 payload/content/request hash；append 时 Owner 再复核 predecessor current，无新增表权限。
- 首次失败后继续消费原 0600 intent，仅允许 fresh draft 的动态时间字段不同；原冻结窗口仍由 Owner 校验。
- 聚焦测试：`18 passed`；`git diff --check` 通过。pytest 退出后的 JDBC closed-stream logging warning 为既有测试清理噪声，退出码为 0。

## 下一缺口

schedule approval 在任何审批写入前 fail closed：当前 signed `solution.ecommerce.growth@1.8.0` 不含 `ecommerce_product_event_schedule.py`、`ecommerce_product_event_binding.py`、`ecommerce_product_event_command.py`、`ecommerce_product_event_control.py`，且未声明可选 `ecommerce_growth_event_control`。这些模块只存在于后续已提交的方案包源码。不得从工作区源码冒充已安装包执行；下一波必须生成不可变 signed successor，完成正式安装/配置/切换后再续跑 policy/control/occurrence。

