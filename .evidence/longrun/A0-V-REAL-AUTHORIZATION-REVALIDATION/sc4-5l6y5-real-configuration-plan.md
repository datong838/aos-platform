# SC4-5L6Y5 十二源真实配置实施计划

2026-09-16；基线 b4314cf0；m1 串行、不 push、230 L0 挂起。承接完整源组调度设计与 Y4 managed-worker 方案。用户持续开发授权适用；不将隔离测试视作真实经营完成。

## 目标与顺序

Y5a 只读盘点：主库以 READ ONLY 事务读取迁移、当前安装/代次、源配置身份、已有图/调度/控制；不读取连接配置或客户明细。从当前包目录检查十二 Mapping/schema/masking 并用原解析、编译合同核验。目录内容检查不等于签名/current安装验证。产物记录缺口，不能自动授予调用权限。

Y5b 可审查配置生成：通过当前 installation baseline 的原签名 artifact reader 读取十二映射，原 derive_mapping_read_spec/compile_snapshot_mapping/verify_graph_read_spec 检查；生成标准三节点图，不复制十二份常量。先验证同源/schema/masking和完整成员；保留原 P01/P02 图，仅在精确不一致且有明确差异方案时修改。配置预览不读源。

Y5c 配置登记：原受保护 graph API 和持久 schedule API 创建缺失配置；所有新 schedule 明确 disabled，未知提交只读原 ID，禁止换 ID 重发。已存在不一致则停止该项。不能把 Phase5 内存 schedule 当主库配置，也不能通过 SQL 直接插图/调度/Run。控制、选择、绑定经原 Owner，使用当前安装和 source configuration exact refs；十二路共同有效窗口在 Y6 执行准备时审批，避免提前过期。

Y5d 验证：独立连接读取原落库配置，对照签名预览；原有图/调度/运行/输入计数及哈希保持预期，零源读取。Y6 前不启用 worker 或组，不开启旧调度。

## 文件清单

本波只写 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6y5-real-configuration-plan.md`、`y5a-real-configuration-inventory.json`，并对账 `sc4-5l6y-snapshot-group-scheduling-design.md`；同步 docs 下当前生命周期补强接续和 D-waves 清单。后续 Y5b 拟新增 `scripts/a0v_snapshot_configuration_preview.py` 及 `services/aos-api/tests/test_snapshot_configuration_preview.py`，实现前补接口与测试细节。产品 Owner/API 如发现缺陷，另列精确文件和 Red/Green，不隐式扩写。

## 风险及退出条件

主库 a0v_061，Y1–Y4 的 062–066 尚未部署。配置 API 有多个近似路径，必须确认实际路由及持久读回，不能依据 HTTP 200 判断成功。P02 有 13 条控制历史，不等于同一 control revision=13。每项权限和 exact ref 在实际应用时重新核验。

Y5a 退出只说明盘点完成。Y5 退出要求十二源已通过原配置入口落库、disabled、可读回；Y6 才进行备份/克隆迁移/演练、主库受控升级、实际源组观察。Z 原业务 Run 恢复/处置仍独立待办，不伪造历史快照，不用新 Run 冒充旧任务恢复。之后仍需完整建议、exact 评审、内容执行、人审续跑、Wiki 与八工作台经营验收。

## Y5a 新鲜盘点结果

2026-09-16T10:05Z，同一 REPEATABLE READ READ ONLY 事务核验主库：a0v_061，J 安装 active，P01/P02 两个 revision=1 图、两个 disabled 调度；niushop-qyh 源配置 registered 且通过原身份哈希核验。P02 是 8 个 control 身份、13 条历史记录、单身份最高 revision=3，不能称为 revision=13。十二份 Mapping 全部通过原 derive/compile 合同，P03–P12 无图。详见 y5a-real-configuration-inventory.json。零远程源读取、零数据库写入。

实现前读码确认 phase5_schedules 使用内存 Engine；wave_ext 的同路径 POST 才调用 data_os_store.persist_schedule。Y5b/c 须检查实际 app 路由顺序、持久化失败传播和独立读回，不能混用。此次盘点没有证明源库实时连接、数据完整性或业务链完成。
