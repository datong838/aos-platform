# BG-02 当前策略绑定读取并接入保存复核

2026-09-14，基线67e28e91。ProductEventPolicyStore.get_current_binding单查询核对当前策略head/不可变history/当前Case，验证schema、摘要、版本、ACTIVE、exact策略引用和方法引用。Host保存服务在041锁后实际调用，代替只读策略版本；初次未保存仍None，已有策略不允许当前Case漂移。旧get及原Receipt读取保持；读取不是启用权限。

RED4失败：2项缺方法，2项不可变Case历史保护拒绝测试修改。未放松数据库，改为追加后继Case后复测。最终含真实Host接入的33 passed无skip（存储、服务、当前审批），日志/tmp/event-current-{red,green,final,integrated}.log。AR2及diff通过。主库038/代码041，未重启/注册/新建真实业务。

下一波事件启用合同/批准与绑定：以本读取门作为一致性基础，还必须当前签名合同、作用域/窗口/角色/批准、事务Owner和明确开启动作，不能从保存直接启用。后续原批次消费者、Run承接、产品意图持久化、真实首链/八场景/持续观察继续未完成。
