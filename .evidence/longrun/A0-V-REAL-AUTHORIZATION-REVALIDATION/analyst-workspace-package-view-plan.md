# 经营参谋包内 Case/Run 只读投影

基线 78ba0fc1。当前主库旧兼容 Case 列表 GET count=0，仅作读回事实，不推断业务已运行。为新包工作台增加无 I/O 的业务投影，从主机提供的同租户、同读取截止时间的 canonical Case/Run/State authority 快照生成可读列表，保留原始精确 refs；不另建 Case/Run 表、不补造记录。

新增 bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analyst_workspace_view.py 与 services/aos-api/tests/extension_runtime/test_analyst_workspace_view.py。输入版本 aos.analyst-workspace-snapshot/v1，scope、cutoffAt、cases[{case,runs[{authority,state}]}]、truncated；最多50 Case、每Case最多10 Run。每个 canonical payload 独立校验 source hash、schema、租户及跨记录身份，拒绝重复或孤立 Run；只输出展示所需标题、类型、Case生命周期、Run编排生命周期/control及精确来源，不带 createdBy、triggerKey、原始全文等无关字段。

包内函数不授予执行权限，不把 PREPARING 当作完整业务进度，也不把目录计数当经营成效。待下一波主机同事务 snapshot reader + signed installed-package invocation 接线后才可称真实产品读取。当前源码模板可改，已安装的1.7.0签名字节不改；新的纯投影入口及frontend资源需正式后继版本交付。注册九项命令集合不在本波调整。
