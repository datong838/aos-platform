# AR1-c 配置恢复与禁入检查点

2026-09-06，基线c07defcc/AOS-000530；沿用主生命周期Lease。

load_configure_target在显式租户事务读取原accepted sequence1，核对事件hash、严格DTO、操作requestHash及expected_binding_revision。fence已持Installation/operation锁后必须比对原请求generation/bindingRevision，防止同安装下另一代次被关入口。配置deadline写读共用UTC哈希函数；非configure历史哈希不改。恢复只返回请求数据，无权限/预算或业务许可。

Red12项（含另一同版本代次fence原会成功）；首次相邻83passed/16.33s。补充dict行与重新计算事件摘要仍串配置的反证后，当前最终累计563passed/6既有warnings/94.34s/exit0，包含真实隔离OCI及专用18432临时PG。git diff --check通过。独立Prime只读复审锁顺序与哈希/精确代次一致，无新实质问题；未替代测试运行。

新configure协议仍未共享部署；此前非UTC字符串哈希的未发布记录不能自动兼容新UTC读取，本次仅隔离测试实例且未留下运行配置。无共享迁移、Provider、费用、发布或真实业务写。后端无页面修改/重载，无新增页面验收结论。安装绑定仍disabled/fenced/configRef空；新增业务场景0，整波进行中。

下一段：不可变配置版本权威，当前角色/数据/预算引用验证、先fence再排空/配置提交，启用仍必须单独验证当前条件与真实持有者。配置引用完整不等于有效配置。
