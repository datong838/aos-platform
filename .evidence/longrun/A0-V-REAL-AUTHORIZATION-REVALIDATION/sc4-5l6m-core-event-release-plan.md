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

容器资格预演发现混合导航声明缺少 operation_id；验收器已修复并新增混合项测试（4 passed）。新代码提交后旧构建Receipt的HEAD绑定正确拒绝复验。保留build目录及日志，新建build-v2重新构建、验收和签名，禁止改旧Receipt的HEAD来通过校验。

F→G 顺序细化：使用 scripts/a0v_event_complete_f_retirement.py 固定 F 身份和当前 Policy revision2，先新 exact disable 审批并关闭 automation 事件绑定；再各自审批 fence 与 shrink，实时核对 group/CAS，并由现有服务验证排空与本次 fence Receipt。源schedule必须关闭、未决源执行必须停止。三步各独立intent与Receipt，已有intent禁止重复。完成event收缩后才允许 RuntimeDisableService 禁用F并等待Host完整释放/正式detach；新G尚无已知ID，不预造身份。

## 真实回执后的卸载缺口（a0v_059）
F event disable 与 fence 已真实成功，shrink因 ar2_005 的历史Receipt→当前dispatch行外键拒绝删除入口，整笔回滚。历史回执不可删除，也不可cascade。修复仅解除历史账本对可卸载当前dispatch行的外键；保留Receipt对安装代次runtime的外键、RLS、不可直写权限、操作白名单，以及写函数中对当前dispatch/runtime的锁与精确身份检查。历史记录保存完整dispatch版本及安装/代次，不把历史Receipt当作当前执行授权。
新增 a0v_059 迁移按确切列/目标关系验证待移除外键，仅移除这一条；降级若历史Receipt已无当前dispatch则拒绝，不删除历史来降级。PG测试必须覆盖先写真实event Receipt→移除当前入口→历史可读/负租户不可读、再次调用写函数被拒绝；旧九入口回归。备份克隆预演/全表事务指纹保护后部署，原shrink意图无成功Receipt且exact fence快照未变才允许同key恢复。
