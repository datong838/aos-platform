# 当前验证检查点（完整Task保持ACTIVE）

2026-10-05，m1 HEAD36a707df / authority AOS-001352；本波实现尚未提交。

- private-runtime-adjacent.log：真实disposable PG、私有SCRAM和本地HTTPS JWT；private boundary/原Source approval/原Capacity approval/原Evidence epoch 四文件93passed、7warnings、130.37秒，进程exit0。包含本轮25项private专项；运行收集后新增7项attachment未计入93。
- private-legacy-attachment.log：七个旧SECURITY DEFINER trigger函数的实际CREATE TRIGGER权限拒绝，7passed、25deselected、7warnings、13.98秒，进程exit0。私有登录自主临时表存在，未由Python身份检查替代SQL权限门。
- 七个新增/修改Python文件AST解析通过；已跟踪三个原guard/helper改动diff whitespace检查通过。
- 旧PUBLIC permissive RLS反例及新restrictive修复见private-public-rls-red.log、plan.md；不是仅Python拒绝。

仍未验证：七个原注册trigger在a150权限撤销后完整业务兼容、其他Action非空行隐藏、private配置全部漂移反例。现有旧生命周期测试使用旧独立schema，不能计作a150兼容证明。

现有approved claims固定NO_CAPACITY_NO_START，supplier/policy引用test-only-unverified；未发布正式Source、未验证supplier证明、全域账户唯一及签名consumer、未完成fullSource实际COMMIT。fullSource/formalBoundary/b90 Task继续ACTIVE，不创建交付通过声明。

真库、Host/worker/真实Provider/商城源/旧Run/外部效果均未操作。下一步先补a150原触发器兼容与private epoch竞争，再推进完整正式Source发行；最终自然经营首链、八工作台、观察与发布仍未证明。

## 后续权限修复与实际私有竞争

- 受邀只读督导指出非public同名权限漏检；private-namespace-red.log实际4failed、32deselected、11.75秒。额外schema同名SELECT、同名UPDATE(subject)、PUBLIC SELECT及单独PUBLIC schema USAGE均未被旧审计拒绝，SELECT两模式已由原native SCRAM SQL证明真实可读。
- 最小修复绑定public实际relation OID，显式table/column精确白名单、全部非系统用户schema有效table/column权限及PUBLIC间接schema USAGE审计。private-namespace-special-green.log专项36passed、56.50秒（收集时未包含后加2项竞争）。
- private-epoch-competition.log两项真实并发验证2passed、36deselected、10.48秒：private reader-first的原withdrawal pg_blocking_pids包含实际private后端PID，caller结束后撤销成功且新读拒绝；writer-first在已建立private SERIALIZABLE快照后原撤销提交，旧快照批准claims拒绝。非helper/mock锁证明；仍没有正式Source发布或业务COMMIT。
- 最新扩展相邻private-runtime-adjacent-r2.log终端exit0，106passed、7warnings、152.95秒；尚未包括随后增加PUBLIC列权限及trigger OID反例。

## 最终专项与受邀复核

- private-public-column-trigger-red.log：真实allowed-table PUBLIC UPDATE/INSERT/REFERENCES列权与迁移guard到非public同名表，4failed、38deselected、11.82秒。PUBLIC列权原SQL回读实际True；不是模拟。
- private-boundary-final-special.log：最终42passed、7warnings、66.42秒、exit0，覆盖前述全部权限反例和私有双向真实竞争。最终改动只在private boundary helper与新增测试，原runtime代码路径保持106项相邻时相同；106是此前修订的结果，不伪称最终42加106为单次累计。
- 受邀route_supervisor只读复核确认OID/逐列effective权限和trigger审计修订，无本次新阻断；以最终专项终结关闭这两个具体审计缺口。受邀审查不是独立daemon自主报告/连续值班验收。
- 最终七文件AST解析通过，精确已跟踪guard/helper whitespace检查通过。完整Task继续ACTIVE；原七触发器完整业务兼容、可信数据库固定、完整4ref requestbinding与供应商attestation/policy、registry全域唯一、正式Source actualCOMMIT和consumer仍待后继。

下一步先收集a150原注册触发器业务兼容证据，再精确提交本checkpoint与更新AOS/Prime权威上下文；不宣布fullSource Task完成，不绕过来源和真实业务授权门。

## 原trigger触发执行兼容（不替代完整业务流程）

legacy-trigger-runtime-compatibility-r3.log7passed、42deselected、7warnings、6.62秒、exit0。完整head150隔离DB中读取原public注册trigger的pg_get_triggerdef，仅测试target变为owner TEMP表，保留原timing/event/columns/deferral；原functionOID/body/ACL未改。runtime实际has_function_privilege EXECUTE=false，正常分支仍保留行；非法缺Receipt/terminal变更按原23514/55000拒绝。临时表只有guard所需rowshape，不复制原业务约束，故本证据只关闭PUBLIC撤权后的触发执行兼容，不证明完整业务表安装卸载链。原业务完整生命周期仍总Goal pending。

第一轮Python引号collection error0.55秒，第二轮SQL.format处理fixtureJSON花括号IndexError1failed6passed6.67秒，均测试构造错误，非业务RED；修正后真实7项全部终结。原106相邻、最终42专项与新增7兼容分开计数，未捏造单次155或49累计。当前所有7代码文件AST与code whitespace通过，无UI修改。

部分checkpoint可提交并推进context，fullSource/formalBoundary/b90 Task继续ACTIVE，任何新Task退出仍须正式signed Source publication COMMIT与consumer，全域mapping及自然经营业务证据。
