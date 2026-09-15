# SC4-5l6m EventControl 可选分派生命周期验证

日期：2026-09-16  
基线：`9e352adc`，数据库原语前置提交 `bc81fff6`。

Python Host Service 与最终请求合同已完成。请求固定绑定 CurrentInstallationRef（installation revision、lock hash、overlay revision）、generation、execution epoch、runtime revision、组及组版本、当前 Case/SchedulePolicy、独立审批和幂等键。Service 在同一 serializable 租户事务中依次复验当前安装、原九项签名注册资格、唯一 event-control 声明、两个已签名合同之一的固定内容、`ecommerce_growth_event_dispatch` exact maker-checker 审批，再临时进入 maintainer 调用 a0v_054，最后切回 runtime 读取并核对 request/content hash。

数据库请求也升级为完整 CurrentInstallationRef，runtime installation revision 必须一致。Action 风险新增固定 R2 `internal_event_dispatch_control`，原 event-control、schedule 和 cutover 分类保持。

定向结果 `46 passed`：请求严格解析、审批意图去除 approvalRef 后保持完整、风险门、数据库 expand/replay/fence/shrink、负租户零写、Receipt 不可变和原控制合同均通过。需要专用 `_ti4_test` 数据库的旧审批 PG 套件未混用普通 18434 管理库；它此前的环境名保护正确拒绝了错误数据库，本提交没有把该保护视为产品失败。

本步仍未应用主库迁移、未修改 E 分派。下一步进入第 2/6：把 growth 1.9 纳入 current 四包 OCI 构建/资格 profile，保持其他三包内容 hash 不变。
