# AR1-c 配置命令与持有启用联合检查点

2026-09-06；基线m1@d89dc924/AOS-000535。主AR1-C-LIFECYCLE-PERSISTENCE Lease负责代码；CHECKPOINT子Receipt仅归档证据，不结束主波。

本段把配置/启用命令接纳、当前权限重放检查、精确启用目标、配置修正、同一资源owner的串行健康/提交合并交付，未按每个函数单独推进authority。

- 原Installation CommandReceipt增加可选current_check，旧调用和冻结控制角色矩阵不变；特化Protocol不改变旧实现要求。当前检查先于缓存Receipt，新CAS仅在新handler中验证。
- 配置与enable从immutable accepted/request hash恢复精确generation/bindingRevision/configRef，旧无目标enable不能猜测恢复。
- 当前持久角色/markings覆盖configure/enable，配置授权组合每次重读，不信请求历史roles。
- 配置切换后unknown且disabled/fenced/已有有效引用时可暂存修正版本；不更改生效指针/epoch/ready，避免坏配置只能先启用才能修正。
- Owner保留verify一次性行为；后续control仅在verify成功后串行接纳，全组心跳后执行可信事务；取消/关闭/lease/进程退出先等数据库工作收敛再清理资源。
- 内部enable事务核对Installation/lock/CAS、当前配置/权限/schema/签名、原验证资源集合及owner固定preparation/generation；同事务更新binding enabled/ready/fence/epoch与事件/outbox。前后健康窗口与资源期限均核对。不暴露HTTP或业务执行端口。

验证：enable目标Red→106项相关PG回归通过；current_check/配置服务先Red后Green；真实签名配置联测暴露unknown修正缺陷后修复，配置store39passed。Owner新增8Red→30项owner系列passed7.58s。真实签名OCI/原Registry/Installation/原CommandReceipt/当前持久角色联合先因缺启用接线Red，最终1passed15.48s，内部18类拒绝事务（含末段健康和资源跨期）全部保持禁入，成功由owner心跳驱动启用，stop后资源释放且binding重新禁入。18个内部反证不虚增成18个pytest或业务场景。

最终安全累计范围为extension_runtime全目录，原asset_registry清单/签名/安装/策略/哈希/接线/证据/角色矩阵/Workshop内容投影，原AIP职责、预算合同/静态迁移及预算配置reader；753passed、6既有warnings、109.25s、exit0。没有运行默认共享DSN的AIP预算store集成测试。git diff --check通过。既有JDBC退出日志关闭流警告保留，不改变exit0。

独立Prime只读复审未发现新增实质问题，要求的末尾时效反证已补；其评审不冒充重跑测试。无页面改动，本段不宣称浏览器验收新功能。仅专用OCI context与18432临时PG schema，未改共享库/真实业务数据、未调用Provider、无费用与发布。配置引用仍是明确命名测试权威，实际AIP预算reader虽已有专项验证，正式角色/数据/策略组合、预算hold、业务broker、持久派发/重启对账和完整启停卸载仍未完成；新增业务场景0，AR1-c IN_PROGRESS。

下一段立即进入受控停用：精确目标与Receipt-first接纳、持久fence先提交、随后跨epoch排空核对与disabled收敛、保留资源/配置、不被坏配置或过期预算阻止安全关闭；然后接正式broker/费用及完整生命周期。不把资源stop当作已实现停用命令。
