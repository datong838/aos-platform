# 维护身份门阶段

新增门禁拒绝Owner/thread/base/authority/status/Delivery/缺Lease/重复Lease/receipt漂移/过期或无时区/资源范围缺失。13项新测试通过；相邻累计52passed1failed，旧测试使用当前live authority但旧执行器硬编码AOS-001329导致预期scope消息变成authority拒绝，不修改旧门、不宣称相邻全绿。新Task真实read_task成功，scope及Owner未来Lease一致。

仅实现身份预检，尚无服务停止/隔离窗口/当前迁移入口；代码Schema/备份/演练/源身份和进程绑定待接入。当前权威源和服务未改；Task保持ACTIVE。方案和当前阶段一致，测试只证明身份条件，不能证明迁移完成。

## 真实只读预检接入
已在当前真实环境执行preflight：原Task identity+未来Lease、m1/已提交业务源码、单Alembic head151、九步当前源码离线SQL hashes逐项匹配原执行intent、terminal0和snapshot连续；第二backup/globals哈希与terminal0、独立restore全库窄等价重算；源当前full snapshot==第二份backup source；原service进程fingerprint；结束重新Task/HEAD无漂移。13纯身份测试通过。
当前尚无mutation入口，也尚未将native/strict-fence历史记录转成操作前现场门，源image需继续与backup intent绑定、实际独立restore现场snapshot重读；不以本只读GREEN授予服务停止/迁移权限。已记录live-preflight.json真实读回，不称完整维护完成。
