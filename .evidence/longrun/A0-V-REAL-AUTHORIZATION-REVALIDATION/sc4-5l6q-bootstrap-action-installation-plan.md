# 初始化动作随安装到位，而非人工补表

## 实证
H真实商品源更新生成65事件；诊断Host在ecommerce_analysis_bootstrap_action.py:53 → aip_action_store.py:192抛AipActionNotFound。主库meta_action_type中ecommerce_analysis_bootstrap为0行。既有集成测试review_identity fixture直接插入此类型，因此此前绿色测试没有验证安装交付依赖。此为具体缺口，不修改权限检查以掩盖缺失。

## 顺序
1. 保留单次源观察/finally关源；新增scripts/a0v_h_product_pause.py，用当前Policy5原回执走精确审批/disable，停止继续产生重复unknown，保留已产生历史。
2. 核对动作类型声明及安装元数据注册机制，形成最小安装/配置就绪契约，使全新租户无需开发者补表。继续保留运行时当前action snapshot与角色/marking检查；不得遇到缺失时构造假快照或降低门禁。
3. 先补“未预先seed动作类型”的集成测试，再实现适用的注册/就绪路径；安装、幂等、漂移拒绝、禁止越租户及已有正常动作不被覆盖都需验证。必要的新增文件在确定后追加本方案再编码。
4. 通过真实正式入口恢复H业务流，不重发未知。当前首链Run0，源成功不计经营成功。

## 07:14暂停证据与设计约束
源scr-6554bd62601f4790成功65行/9959ms，finally已关闭schedule；H Policy5 disable Receipt 1114f2f9-3b0f-579d-a440-6e8db5e6bfe0@2，hash sha256:69aa23633312a531d02ee7295b730a36cb8fceeaaec0b0bc00cb323d68d6e033。当前H9needs_attention/56pending，Run0；后续若仍有已领取事务结束需再核对最终数。
meta_action_type为无tenant列、无RLS的旧全局表。因此不采用全局seed或手工补一行。方案细化为安装代次/epoch作用域的内部动作目录：在已有精确审批的event-enable事务中自动登记Host初始化动作定义与源控制Receipt，运行时只读该安装的目录并核对来源，已有全局动作不覆盖。当前全局动作快照校验保留给既有记录，新的安装动作快照携带显式目录Ref，不做无来源fallback；原guard还要强制当前安装目录与proposal snapshot一致。

## 已确定实施清单与契约
- services/aos-api/alembic/versions/a0v_061_installed_bootstrap_action.py：新增RLS不可变目录和限定登记SQL；org/project/installation/generation/epoch/action_id唯一，保留配置及已验证enable Receipt来源。定义为Host分析初始化的内部动作契约，不开放任意动作注册，不读写旧meta_action_type。
- services/aos-api/aos_api/ecommerce_installed_bootstrap_action.py：精确目录写入/读回；固定动作定义、Ref和hash校验，原控制Receipt/binding/runtime必须吻合。目录只是定义，不授予业务执行/对外副作用权限。
- services/aos-api/aos_api/ecommerce_product_event_control_store.py：在已获准enable的同一事务中、控制Receipt完成后登记，回滚一致；已验证当前enable重放也能核对目录。disable不删除历史。
- services/aos-api/aos_api/ecommerce_analysis_bootstrap_action.py、aip_action_store.py：带真实BootstrapGuard的初始化动作快照从当前安装目录取得，guard要求实际快照一致，不能退回全局同名类型。记录携带installedActionRef。
- services/aos-api/aos_api/ecommerce_analysis_bootstrap_authority.py：有installedActionRef时核对租户目录与来源/hash；旧记录无此Ref时保留原全局当前快照核对。角色/marking/maker-checker和特殊初始化执行门完全不放宽。
- 新增tests/extension_runtime/test_installed_bootstrap_action_pg.py与空环境formal-bootstrap用例；现有fixture不要再把预seed作为生产就绪证据。测试全新scope enable→目录自动到位→真实Action/Task初始暂停，无Agent执行；篡改Ref/tenant/epoch/审批来源拒绝，重复enable不增生，事务失败全部回滚。
- 后续单独固定061克隆迁移部署器；先测试，再克隆全表指纹，最后主库部署/加载。现阶段不运行任何手动补Action数据命令。

补充：旧控制 Receipt 重放保持纯读取，不在重放时补写目录；已禁用策略的历史重放仍返回原 Receipt。只有新一次经 Owner 审批的 enable 事务建立目录。首次测试实际停在缺少测试数据库环境变量，尚不能算产品逻辑红灯，需在隔离数据库重新执行。

## 部署前验证与执行器

新增 `scripts/a0v_installed_bootstrap_action_deploy.py`，沿用已验证的完整备份→隔离恢复→同事务逐表指纹比对→主库增量迁移路径，固定 a0v_060→a0v_061、当前 5L6Q 租约和独立状态目录。只新增空动作目录与受限函数，不回填 H 或历史安装。验证 runtime 仅有读取和限定函数执行权限、maintainer 无函数执行、PUBLIC 无权限、RLS 与不可改写触发器。主库应用前必须保留恢复证据。H 事件策略及源调度保持关闭；加载新 Host 后须走新的正式 enable，不重放旧已禁用命令补写目录。

测试修订理由：原 start 测试修改全局 ActionType 名称已不影响安装动作，因此改为安装配置漂移拒绝；另有目录引用哈希、未知 entry、执行 epoch、禁用与 fence 的拒绝测试。旧无 installedActionRef 的历史快照测试仍检查原全局记录，未削弱兼容路径。目录启用三项测试已通过，完整首链初始化在无全局动作情况下已通过，尚未应用到主库，也没有真实业务成功结论。

代码边界复核：目录安装钩子应置于 `aos_api/ecommerce_product_event_control_host_service.py` 的已授权 enable 回调内，控制前后仍执行 Owner/审批校验，事务不变。底层 `ecommerce_product_event_control_store.py` 继续作为通用 CAS 传输层，不强加分析域目录依赖。这能保持旧传输层测试与调用语义，真实 Host 启用仍自动建立目录。新增外键也意味着历史 042 迁移不能越过 061 直接回退；测试应验证受依赖保护的拒绝，不去删除真实依赖或放宽外键。

## 本波交付事实（2026-09-16 07:32）

- 新目录、061迁移、Host enable 原事务安装、guard 读取与显式安装引用校验已实现；底层 CAS 传输保持原语义。
- 隔离全迁移数据库：150 passed（控制、初始化、目录、历史审批与正式入口），7项既有依赖警告。完整初始化 fixture 刻意删除全局 bootstrap 行，仍生成 AnalysisRuntimeReceipt、暂停 TaskRun 和带安装引用的提案；无审批事件。它仍是 fixture 验证，不能报为真实经营链成功。
- 实际备份恢复副本 `aos_installed_bootstrap_action_20260916_test`：543张原有表迁移前后指纹一致，新增目录0行；runtime仅SELECT/受限函数执行，maintainer不能执行，PUBLIC禁止，RLS及不可变触发器通过。
- 主库已正式 a0v_060→a0v_061；同事务原有数据指纹不变，新增目录空。备份后自然变化仅 runtime event/operation/outbox/resource lease 四表，已在 apply 证据列明，未伪装静止状态。
- 私有部署证据：`.aos-recovery-20260916/state/installed-bootstrap-action-deployment/{prepare,transaction-verified,apply}.json`，完整备份保留。
- 主库业务Run成功数仍0；H策略关闭、源调度关闭。下一波：核验 H 运行状态、制定并执行正式服务加载/恢复，在新审批启用事务中验证自动目录，再开启真实首链。旧9 unknown须保留且通过原060精确证明流程处理，不能直接重试或改写。
