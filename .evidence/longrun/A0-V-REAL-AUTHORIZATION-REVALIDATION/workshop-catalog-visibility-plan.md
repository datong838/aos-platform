# 工作台目录可见性与恢复入口方案

基线 cf078885，2026-09-12。实时 modules 接口 count=0；旧目录明确排除 runtime lock。不能移除此隔离或伪造八个菜单，正式登记仍待具体访问范围答复。

修改 apps/web/src/components/workshop/InstalledModuleNavigation.tsx 与 EcommerceWorkshopHost.tsx：空目录只声明没有可见入口，不推断未安装；导航显示加载、失败、无权、旧快照状态，用现有 reload 提供恢复入口。保留实际菜单与既有只读策略。对应测试验证空目录重读恢复及故障；运行相关测试、类型检查、真实浏览器和持续运行观测。

不改变 API、安装、权限或调度；仅修正可见性说明，不代表八工作台或经营首链完成。可通过还原两个组件回滚。
