# 休眠中断与宿主异常链验证

2026-09-12，基线42d1cc15。pmset原始系统记录显示12:34:45 Low Power Sleep（1%电量），1372秒后12:57:37唤醒。主库末次续租04:34:24Z，expiresAt04:37:24Z；Host日志04:57:42Z终止。唤醒时旧租约已过期，不把此事归因于模型慢响应或SDK帧预算。

当前绑定unknown/desired enabled/enabled false/fenced true revision5，三资源cleanup_state released且observed_release=true。Docker仅剩两个PG容器。自然经营链未运行，无恢复成功声明。

宿主旧日志只记录最后RuntimeConflict栈，原错误链不可从旧进程补回。本次脚本增加errorChain，最多16异常、每异常32帧，仅类型/位置/关系；不含message、args、locals或源码。先红2 failed/4 passed，后脚本+RuntimeHost 27 passed。未改变运行调度、过期判定或权限。

下一波：既有RuntimeDisableService冻住本安装当前revision5和generation，正常Host消费并回读disabled_committed；再制定已启用未dispatch实例的恢复/卸载证明合同。a0v_020明确禁止enable成功历史，所以不得直接套用其configured_unactivated分支。登记权限仍待回复、SSH仍拒绝未恢复。
