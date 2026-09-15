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

安装执行文件：scripts/a0v_ecommerce_event_complete_reinstall.py 固定前序F、后继G独立输出目录和core1.4/growth1.10版本。沿用已经真实验证的受控安装服务；创建G前必须F禁用资源排空且正式detach，不能因收缩或登记成功跳过旧安装生命周期。G准备前Host只在F全部退役后改读新签名根；API独立重载。仍保留所有旧E/F脚本和历史Receipt。

G安装实测后精确身份：installation 4b081ad7-2cf6-4188-bc18-870726da1262，generation 1c8d9a2d-0a1b-4caa-9fef-528568fd2629，初始runtime revision4/epoch3；lock sha256:3997ccbf5729e46dd7947db59d3093b9963e5e74c5bdfa627003c8fbacfad1cc；config bf6875bf-c01b-46ad-bb1f-d7c634369f5e@1 / sha256:e420c697c1969955a8d44ed3b7e2c0497416c72436433fdc9fcd982bd942e796。F detach Receipt3a0aa78f-c6c7-4584-9792-b6491e16f67d；当前九入口legacy/fenced/groupRevision10。
新增 scripts/a0v_event_complete_successor_business.py 按上述固定身份登记；随后 scripts/a0v_event_complete_successor_cutover.py 绑定实际登记Receipt、新独立审批/操作ID完成接管。旧F脚本不改，G不可复用F审批。

G接管已resumed，后续source/profile脚本以G当前binding6/epoch3及group11为固定检查。新G Product授权为首版本（安装维度）；源schedule沿旧绑定版本继续CAS。业务Case不重建：从F成功的Policy revision2与Case version4生成Policy revision3/Case version5，保留业务历史ID、换成G current SourceSelection。新增a0v_event_complete_product_{preflight,authority,policy,enable,source_once}.py，仅通过正式Owner/服务/API推进。新源执行有自己幂等intent，不重新发送F旧run；新的当前数据更新会形成独立来源证据。
G源执行预检必须按policy_id与policy_revision=3精确选择新事件绑定；同业务Policy保留F revision2的disabled绑定，不能任取首行。正式事件服务与数据库仍独立复核G安装/代次/epoch及有效期。

G实测自然产生65个occurrence，但分析承接被通用dispatcher标记unknown/needs_attention，Run=0；原dispatcher吞掉异常而无诊断。源run已成功，不重发。先用新exact审批关闭G当前Policy revision3事件绑定（不停止Host、不改epoch），保留unknown及pending记录；新增 scripts/a0v_event_complete_g_pause.py 仅approve/disable，当前binding revision1 CAS，不提供重新启用/重试路径。后续补安全失败诊断与正式Receipt核对恢复，禁止SQL重置unknown。

## G 分析前置条件恢复波次
实时只读检查：65 occurrence = 17 needs_attention + 48 pending，目标 Case Run=0。六个角色实际 CapabilityBinding 旧评估于2026-09-12到期；正式 preview 均返回 MODEL_ROUTE_BLOCKED / PROVIDER_HEALTH_UNAVAILABLE，不能仅刷新时间戳。私有证据 successor-g/analysis-pause/capability-preview.json。此为已证明的前置缺口，不声称已捕获17次原始异常。
下一波：1读取现有模型健康探针及当前exact依赖；2通过 scripts/a0v_real_text_provider_health.py 独立journal单次真实健康检查；3通过正式CapabilityBinding evaluate按当前version与依赖重新评估；4重新读取职责ready/complete及其他阻断；5审查unknown正式恢复接口，禁止SQL清理/重发；6留证据并进入有效窗口下自然首链。新健康检查不包含客户数据，仅固定公共健康提示。若旧网络/模型授权失效，则登记并通过现有后继配置流程修复，不能改旧权威。
本波文件：scripts/a0v_event_complete_g_pause.py；测试 services/aos-api/tests/extension_runtime/test_a0v_event_complete_g_pause.py。检查既有intent拒绝重发；暂停不修改Host epoch、不清理记录。所有产物阶段尚待真实验证。
