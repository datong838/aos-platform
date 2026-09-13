# BG-02 事件策略存储约束验证

2026-09-14，基线76966614。039仅替换既有策略revision表类型/节奏check，保持旧函数、历史迁移、ACL/RLS与三表权威不变。事件schema必须匹配product_event/event；NULL或交叉类型拒绝。downgrade遇到事件历史拒绝，零事件可恢复原约束。

原schema/包事件合同/旧定时合同累计40项通过，唯一alembic head为a0v_039；反向schema组合负例曾1 failed/1 passed，修正后全绿。临时PG验证原策略行保持、旧函数定义不变、非法组合拒绝以及非破坏回退。diff与memory-validate通过。主库仍038，未部署039、未重启Host/API，未新增任何真实事件策略或Case/Run。

下一片实现事件写入的严格载荷/Case同事务核验设计及隔离持久化；复用包内ProductEventSchedulePolicy、同一SchedulePolicyRevision历史与Receipt。新能力未闭合前不加入已证明运行操作集合，后续主库部署另有完整备份/恢复验证。
