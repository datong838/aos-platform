# SC4-3c3a 通用启动入口隔离验证

2026-09-14，基线31e2e9d8，m1单写者。

按analysis-bootstrap-runtime-design.md补充方案，通用StartGate识别初始化Action及预览purpose，拒绝产生queued经营Run。动作快照id也受检查，避免借普通Action复用初始化Preview。专用入口、风险例外、Action注册均未启用。原maker不能自批规则保留。

红测：两项实际隔离库候选均在已有approved Proposal下错误STARTED（/tmp/a0v-bootstrap-generic-red.log），修复后累计19 passed、7既有警告、7.95秒（/tmp/a0v-bootstrap-generic-green.log）。覆盖两种误用、原正常启动与幂等、外层回滚、真实初始检查点及启动预览。

测试中的Action/角色/Logic依赖为明确fixture；无主租户改动，无真实经营执行。通用入口拒绝不是专用入口完成。下一SC4-3c3b当前身份/来源/精确任务绑定与专用入口，随后c4和SC4-4完整START。
