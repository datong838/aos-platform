# 维护身份门阶段

新增门禁拒绝Owner/thread/base/authority/status/Delivery/缺Lease/重复Lease/receipt漂移/过期或无时区/资源范围缺失。13项新测试通过；相邻累计52passed1failed，旧测试使用当前live authority但旧执行器硬编码AOS-001329导致预期scope消息变成authority拒绝，不修改旧门、不宣称相邻全绿。新Task真实read_task成功，scope及Owner未来Lease一致。

仅实现身份预检，尚无服务停止/隔离窗口/当前迁移入口；代码Schema/备份/演练/源身份和进程绑定待接入。当前权威源和服务未改；Task保持ACTIVE。方案和当前阶段一致，测试只证明身份条件，不能证明迁移完成。

## 真实只读预检接入
已在当前真实环境执行preflight：原Task identity+未来Lease、m1/已提交业务源码、单Alembic head151、九步当前源码离线SQL hashes逐项匹配原执行intent、terminal0和snapshot连续；第二backup/globals哈希与terminal0、独立restore全库窄等价重算；源当前full snapshot==第二份backup source；原service进程fingerprint；结束重新Task/HEAD无漂移。13纯身份测试通过。
当前尚无mutation入口，也尚未将native/strict-fence历史记录转成操作前现场门，源image需继续与backup intent绑定、实际独立restore现场snapshot重读；不以本只读GREEN授予服务停止/迁移权限。已记录live-preflight.json真实读回，不称完整维护完成。

## 现场资源与窗口日志阶段
现场源Id/Image/唯一volume匹配第二backup intent、secondrestore身份镜像卷固定、现场full snapshot等于原saved再窄等价验证源，实际只读GREEN。资源5反例RED后GREEN。新journal实际文件测试：Timeout只留intent、重发operation不调用；head变化拒绝前序binding、failed结果不生成done。最终20passed；这些纯执行器边界测试不证明真实窗口/数据库迁移。
尚未接入真实stop/fence/备份/迁移operation；服务当前运行，源142未改。newTask保持ACTIVE。

## 执行时身份复核检查点
创建journal后的HEAD/branch/Task漂移反例真实RED：三例均已调用operation（调用数1，期望0）；另外三例因新复核入口缺失失败，18passed/6failed。最小增加每步写attempt前与写后两次实时Task/Lease/authority和m1/HEAD复核。专项24passed；专项与旧维护保护累计63passed/1deselected。唯一排除为既有旧执行器硬编码1329、测试依赖当前1369权威的错误消息断言，原失败仍保留，不宣称旧整套全绿。

真实只读`_require_live_binding`通过：Task/Lease/AOS-001369/m1@465fa10f一致，证据live-journal-binding.json；没有调用journal operation，没有服务或数据库副作用。方案与实现均明确两次采样不是原子锁，真实operation仍须自身资源复核。完整当前迁移/重启/八工作台与自然首链未通过，Task保持ACTIVE。
