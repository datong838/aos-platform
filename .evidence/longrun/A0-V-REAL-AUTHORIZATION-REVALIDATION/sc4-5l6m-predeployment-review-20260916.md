# 第 3/6 步：签名前复验及生命周期审查纠正

Rules：m1 串行；沿已提交方案；最小改动；保护主库和用户改动；不 push；230 L0 挂起。

2026-09-16，基线 `20b60b0e`。

## 已完成的新鲜验证

在已提交 profile 基线上重新资格验证，结果 QUALIFICATION_GREEN；core/niushop/growth 精确注册 1/2/25，各 2048 心跳并 released。签名 preflight 为 PREFLIGHT_GREEN，构建树仍为 `sha256:4756ec28f4d7cc4c8670c572df5b0c0e7f1b6ac33e1882c89d2a6bc0e66dcd2c`。未调用 apply，Registry/安装变更均为零。

阶段验证器显式选择 `--phase ar2-7`：扫描 1957，分类 198，迁移 93，全部错误数组为空。此前默认 ar2-0 的 hash 报告属于原始阶段比较，不能据此声称当前阶段长期有未解决 hash 漂移；原验证文档该结论由本条纠正。

## 部署前发现的未闭合项

不能将上一条生命周期 46 项测试通过解释为端到端生命周期已完成：

1. `ar2_016` validation rollback 只接受 committed/validated，E 已 resumed。后继安装应使用已有 ar2_017 disable/detach 路径，不能按原方案调用 validation rollback。扩展/收缩改变全组版本后，还需证明原 activation 引用与 disable/detach 快照兼容。
2. `a0v_054` shrink 只检查控制行 fence，没有方案要求的前一阶段 exact Receipt，也没有显式 drain 证据。需补正确性测试和实现后才能迁移主库。
3. Service 目前测试覆盖 DTO、风险分类及 SQL 原语，没有实际验证签名资格→独立审批→SQL→Receipt 的完整同事务组合。SQL 测试使用 `$1::text` 占位 canonical 函数，不能证明生产 canonical hash 与 Python readback 一致。必须改用真实 canonical 函数测试。
4. 旧审批 PG 测试因 `_ti4_test` 环境门拒绝而没有运行；需用现有标准自动创建的隔离数据库完成该测试，不可计入通过。

## 接续任务与范围

第 3/6 步先完成上述审查修复，再持久签名与 Registry。修改前补充 `sc4-5l6m-event-control-dispatch-lifecycle-plan.md` 的 exact predecessor、drain、resumed disable/detach 和真实 Service 集成测试退出条件；预计文件为现有 a0v_054、ecommerce_event_control_dispatch_lifecycle.py、其测试及必要的生命周期桥接文件。保持现有 E 工作状态，不以新增测试或截图替代可卸载恢复的真实闭环。
