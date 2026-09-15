# 核心事件能力发布闭环补强方案

真实源执行 scr-cea6cfa2f0ae47da 成功写入65行（11199ms），自然Host发现候选，却因安装core1.3.0不声明 ecommerce_core_product_event_windows 被IPC拒绝。180秒观察无occurrence，源schedule已finally关闭。已有源码不能替代签名包可调用证据。

## 实施清单
1. 保留当前F与历史包，生成不可变 core1.4.0：从core1.3复制，仅增加经审查的事件窗口计算及依赖三个纯计算/验证文件、注册入口与manifest操作声明。
2. 生成 growth1.10.0：从growth1.9复制，仅提升core最低依赖至1.4.0、版本和八工作台自引用，避免解析到无能力的core1.3。
3. 新固定构建profile（core1.4/growth1.10/niushop1.23/operations1.2），不修改已发布旧候选或旧profile。包内真实隔离RuntimeSession调用事件窗口计算并校验原请求hash、确定deadline；不能只检查registration/heartbeat。
4. 原签名17包保留，新核心/增长版本签名和内部Registry登记后，再计划固定F→G的禁用排空、detach、安装配置和exact接管。无直接写旧安装lock、无修改旧签名目录。
5. 新安装下重新建立当前源窗口与Case/Policy后继，执行真实Product更新并由自然消费者生成occurrence/Run。不得复活已过期窗口/伪造新source timestamp。
6. 继续经营分析有来源建议、exact评审、内容能力任务及产物、人工评审自动续跑、Wiki候选；扩展八工作台真实经营计划并观察。未到发布决定阶段。

验证目录：services/aos-api/tests/extension_runtime/；候选目录 bundles/candidates/ecommerce/domain.ecommerce.core/1.4.0 与 solution.ecommerce.growth/1.10.0；执行器 scripts/prepare_ecommerce_event_candidates.py、build_ecommerce_event_candidates.py。
