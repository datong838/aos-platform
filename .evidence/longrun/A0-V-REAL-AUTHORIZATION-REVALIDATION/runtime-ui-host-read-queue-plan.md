# N8 UI → 原宿主签名读取投递技术方案

基线41ed8fc8。此方案补充原AR2 N7/N8、runtime-workshop-routed-ui-plan，不另起业务主线。已确认API18181与运行宿主PID6606分进程；LivePreparedJobDirectory为进程内真实实例目录，CurrentInstalledPackageInvoker只能在持有PreparedJob的原宿主调用。现有PostgresRuntimeAttemptStore支持signed_read、owner token、期限、immutable事件和排空恢复，必须复用。

## 目标与边界

只开放固定只读操作 analyst_workspace_view_v1。Web发起请求只提交当前RuntimeUiInvocationTarget、moduleId=ecommerce.analyst、caseLimit/runLimit；不接受SQL、URL、包路径、任意operation或原始业务payload。服务端绑定当前subject与TenantScope。队列不是执行授权，不改变九项业务命令dispatch/cutover，不创建第二个包实例。

宿主原有租户assignment串行领取本租户任务；请求目标必须命中自身LivePreparedJob。Claim前/完成前均核当前安装、signed UI声明与module权限、当前成员与markings。原canonical snapshot reader在repeatable read/serializable事务形成快照，包投影仅消费该快照。IPC在事务外，通过CurrentInstalledPackageInvoker进入原实例；读取执行进入既有signed_read Attempt及排空协议。

## 数据与状态

新增extension_runtime_ui_read_request，租户复合主键request_id、唯一(subject,idempotency_key)、request_hash及不可变target/limits/subject/deadline。接受时仅requested；claimed绑定一次owner_token_hash、attempt_id与snapshot_hash。成功写result_hash和有限result_json并进入succeeded；拒绝/失败/期限到进入denied/failed/expired。终态不可变，不重置requested；同键不同hash冲突，同键终态仅回读。命令体与provider数据不能经该表进入宿主。

已有extension_runtime_execution_attempt仍是实际调用/排空权威。请求行仅投递状态，不凭state=succeeded授业务执行许可；实际worker须先完成Attempt再封存同一结果。崩溃后已领取或结果不明任务终结为failed/expired，不重放；用户以后新读取使用新请求键、重新读当前事实。取消浏览器等待不取消原运行宿主或其它请求。

DB隔离沿用现有org_id/project_id GUC+FORCE RLS。API不能更新claim/结果或直接写Attempt，宿主不能代替主体凭队列标记执行；使用固定SECURITY DEFINER接入函数/明确角色，限定search_path并撤销PUBLIC，禁止向Web角色授予成员表UPDATE。当前诊断profile不是生产身份达标证据。

## 分片及退出条件（自动衔接）

1. UQ1：严格请求/结果合同与a0v_031加法迁移，fixed read kind、状态/immutable/RLS/权限；真实隔离PG通过负租户与无越权修改测试，主库暂不迁移。
2. UQ2：当前主体/签名门禁下入队与同键回读、限流和期限、exact target；拒绝不写入，未知不重发。
3. UQ3：既有宿主assignment中的具体只读消费者，复用Attempt、源快照与原PreparedJob；双worker/失效代次/中途撤权/关闭排空测试。
4. UQ4：独立API提交/查询及Web等待结果，旧资源失效即撤下，命令入口继续关闭；不暴露原始异常或跨租户结果。
5. UQ5：后继growth包加入纯投影invoke分支及签名前端资源，operations-base另包保持7+1；OCI及资源交付逐hash验证，旧包不可覆盖。
6. UQ6：备份与规范主库迁移、原宿主升级/恢复、新包安装配置，通过真实页面及隔离租户读取；新审批主体仍必须是现实独立身份，不自签评审。
7. UQ7：回到真实首链与八场景，源更新/Case/Run/分析/exact评审/内容任务/受控能力/产物/续跑/复盘Wiki逐证据验收，再连续观察和发布决定。

## 文件计划

UQ1修改services/aos-api/alembic/versions/a0v_031_runtime_ui_read_request.py，新增extension_runtime/ui_read_contracts.py与tests/extension_runtime对应合同/PG测试。其后文件在每个分片开工前细化，所有结果补入closure-manifest与项目两份接续文档。任何单元GREEN都不把UQ6/UQ7标完成。

## UQ2-A 入队存储切片（基线6ca66615，编码前补充）

新增 extension_runtime/ui_read_store.py 与 tests/extension_runtime/test_ui_read_store_pg.py；复用当前成员事实与canonical_sha256。仅内部事务端口，暂不授予API写入权限或暴露接口。签名模块和当前UI门禁由UQ2-B具体接入服务完成，在此之前不能宣布UQ2完成。

方法要求现有 READ COMMITTED 事务与同租户GUC，当前成员读锁；按租户 advisory transaction lock 串行所有入队，先核同主体同键记录：同摘要原样返回、不同摘要拒绝。新请求限制同租户未过期requested/claimed最多64条、同主体最多8条；期限固定数据库时间后60秒，UUID由服务端生成。过期请求不自动重放也不改历史。所有拒绝在INSERT前发生，数据库trigger再次核当前绑定版本。该端口不执行包、无成员修改、无自建事务commit。

验证使用隔离真实PG，核同键回读、冲突、主体隔离、成员撤销、并发额度、调用者回滚。规范请求摘要须与UQ1数据库算法一致。未集成签名门禁前不增加角色INSERT/函数EXECUTE授权。

## UQ2-B 当前签名资源接入（基线e4da3721，编码前补充）

新增 extension_runtime/ui_read_admission.py 和对应测试。具体服务依赖既有 RuntimeWorkshopCatalog；不得接收Web提供的目录条目/权限标志。调用者事务内锁住当前成员及所需markings，使用这些当前事实重新加载已验hash的目录。只接受唯一ecommerce.analyst模块、完全相同的七字段target、固定readOperationClaim；目录角色/markings再明确比对，才进入UQ2-A存储。相同键回读同样先重新校验资源和当前权限。目录自身读取使用独立只读快照；最后INSERT的binding guard核epoch/revision，宿主领取仍必须重新做全部门禁，因此入队不是执行授权。暂不新增HTTP或数据库写角色授权。

退出：门禁拒绝时存储调用为零，旧资源/撤权/command-only声明/错模块/错scope/重复模块均拒绝，合法固定读取交给原存储。该切片完成仍需受限数据库接点及UQ3消费者后才能真实调用。
