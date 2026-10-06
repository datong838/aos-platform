# 当前142→151维护合同

依据231主计划、现有142维护方案及完整独立恢复151/第二份142备份验收。当前权威源仍142且完整snapshot未变；API启动门已动态追随代码head151，不修改它。当前m1单写，Host/worker/Provider关闭、不push。

文件：scripts/a0v_current_151_maintenance.py、scripts/tests/test_a0v_current_151_maintenance.py；本evidence目录；aos-recovery/current151-*；明确三个maintenance/current-preview资源。保留旧135→142执行器。先实现纯门禁（Task/Lease exact receipt、不已Delivery、未来expiry、原currentauthority/冻结HEAD、原142源镜像卷/进程fingerprint、151代码head/冻结SQL、九步演练/第二备份hash及snapshot绑定），RED反例后最小实现。旧公共source identity/窗口/进程指纹工具可复用，不放宽旧authority硬编码门。

执行序列：精确原进程停止→隔绝TCP并核listen空/客户端0/prepared0→窗口内独立一致备份和恢复（所有原备份保留）→九步hash SQL一次执行→完整旧数据/元数据和目录允许差异审计、151精确fence→恢复原listen设置并验证→原签名来源最新API/Web启动→端口/启动时间/健康/版本/租户/八工作台浏览器验收。每步O_EXCL intent+终端，超时未知只读对账，不重发；失败保留封闭窗口和原数据，先诊断最小修复；不得未经迁移验证恢复旧不匹配API。

当前仅注册及纯门禁开发；不因Task存在即停止服务或迁移当前库。权限身份/审批预算保持原禁入，不把维护通过当正式首链。

## 只读预检绑定实现
原两个代码文件内补preflight(thread)：新Task身份门→m1/当前HEAD/已提交业务代码→Alembic单head151→九步SQL当前源码离线重生成逐字hash与原intent匹配、terminal0、快照连续→第二backup SHA/globalsSHA/terminal0及独立restore全库窄等价重算→严格fence/native151成功记录作为历史线索（后续当前操作需再次实际验证）→源Docker身份及完整snapshot匹配第二备份→原API/Web进程fingerprint读取→终点HEAD/Task再读。返回preflight only，不提供停止/迁移执行入口。不能把可伪造历史标签单独当权限。
