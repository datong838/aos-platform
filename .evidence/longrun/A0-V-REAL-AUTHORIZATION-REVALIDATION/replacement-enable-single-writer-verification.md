# 替换启用单写者与卸载只读历史验证

2026-09-13 03:38，基线e0ddecba。enable_commit新增旧父leaf保护及前驱当前禁入/排空核验，replacement_enable_guard使用原安装lineage锁与前驱binding行锁，读取原成功disable的disabled_committed事件，严格比对generation/revision/epoch/lock/hash和资源保留bool。缺binding、多代、未排空、错误凭据或跨租户拒绝；首装无前驱保持原行为。前驱锁持到新enable事务提交，测试实际第二连接在锁释放前不能修改旧binding。

RED：旧父已有active child但启用不拒绝，1 failed/3 passed；新PG守卫缺模块collection error。实现后18 passed，追加3个PG反例及入口前驱未证实反例；enable/disable/configuration等48 passed/1 skipped（OCI未开启）。随后显式开启OCI真实签名生命周期，不把skip当通过。

OCI发现旧代码uninstall历史表FOR SHARE需UPDATE权，换回e0ddecba启用模块后仍相同InsufficientPrivilege，8.16秒复现。修复runtime_uninstall.py只锁可变安装头i，当前revision条件和不可变r读取保留；不增加权限。夹具验证aos_app无revision UPDATE权。首次修复后业务流程通过但旧全引擎空容器断言误计真实Host三容器；改为严格前后集合一致，既证明本轮资源全部释放又保护原有容器，未移除任何真实容器。

最终新守卫/启用入口/批准卸载/真实签名OCI停用卸载重装27 passed，10.68秒，7既有warning。先前邻接48项通过；新PG fixture是权威形状测试而非真实业务切换。AR2 ar2-7 1810/158/93，五类错误为空；git diff --check通过。

范围限制：实际API/Host尚未加载修复；Niushop1.5仍仅Registry published，当前1.4安装仍运行。尚未执行替换。缺前驱runtime绑定/排空凭据的迁移拒绝，未扩展纯内容前驱到运行包；旧父有active子即拒绝重启，需要leaf-first恢复。既有子→父锁序未重构，冲突由PG回滚，不能声称通用零停机切换已完成。

下一波：制定当前1.4@7到已签名1.5的exact replacement实例方案，复用原Composition/Installation/Runtime Owner，先新代prepare/verify但不开启业务；部署新API/Host基线后再禁入旧代并排空、配置/启用新代。保留源配置与P01历史Receipt，P02使用新实例ref和新审批，不复用原耗尽额度；商品空详情合同仍需处理或由首读明确拒绝。
