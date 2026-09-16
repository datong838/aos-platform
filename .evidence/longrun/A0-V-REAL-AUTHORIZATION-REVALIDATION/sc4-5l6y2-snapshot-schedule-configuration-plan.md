# SC4-5L6Y2 安装绑定的源组配置与禁入

基线m1 b5e67aa1，主库仍061；Y1/062只在隔离库验证。Rules沿用原总方案：先方案、单写m1、原Owner、Receipt-first、双租户、不push、230L0挂起。当前不执行主库迁移或真实源读取。

## 产品行为与状态

组配置有独立definitionId（不是某次运行的groupId），绑定同一安装/代次、十二条exact ScheduleControlBinding、当前导出的关系策略、周期。用户配置后初始disabled；enable时重新检查全组控制、原安装/预算/角色和导出策略，才同时启用十二条受管调度。运行由Y3/Y4固定执行器负责，配置本身不读取源。

只有disabled配置可以修改成员或周期，并要求原所有成员运行已停止、无未知结果。disable不依赖源可连接或未过期，先关闭组及所有成员调度，但保留成员归属，不能落回单路cron继续执行。retire只允许disabled且全部运行已确认停止，才释放当前成员归属；历史Revision/Receipt不删除，原单路调度保留disabled，不能悄悄自动恢复。重新安装须新当前控制与配置，旧安装记录不构成权限。

同一scope/schedule最多属于一个当前组。任何已归组的成员都不得走单路手工/cron/recovery领取入口；组disabled仍然禁止单路绕行。移除归属必须经正式retire及在途检查。旧未归组调度保持现有行为。

## 原权限与锁序

配置/enable用原PipelineSnapshotGroupOwner及PipelineSnapshotGroupPolicyOwner检查全十二源和当前签名关系策略；禁止调用者传success。停用/退役复用CurrentConfigurationPermission与原PostgresInstallationStore的当前成员/安装markings校验，不复制admin角色判断，不要求重新读取来源或再次取得已过期的读预算。

锁序固定为安装当前权限/definition head→原完整组controls→按schedule_id锁成员调度。单路领取在原schedule行锁内检查归属后拒绝，无需再锁definition head。首次归组与单路领取共用schedule行锁：谁先提交，其结果由后者重新读取并拒绝冲突，不能出现检查后跨事务插入窗口。

## 分段执行（仍属于Y2）

Y2a 配置Owner与存储：新增a0v_063_snapshot_schedule_definition.py、pipeline_snapshot_schedule_definition.py及对应完整PG测试。Revision不可变，Head原版本CAS，当前成员唯一；Revision精确引用原ScheduleControlBinding与安装身份。原组策略验证与成员启停同事务，任一失败全部回滚；request hash绑定actor、操作、definition、原expected ref及完整输入，成功重放返回原Receipt不重复改变当前head。

Y2b 产品控制API和领取围栏：修改pipeline_control_service.py、routers/pipeline_controls.py、pipeline_schedule_claim.py、qyh_cron_scheduler.py、pipeline_snapshot_schedule_claim.py并加针对性回归。使用原principal与Idempotency-Key，严格请求格式、不暴露凭证。组执行领取传当前definition exact ref，要求head enabled及成员全覆盖；NoDefinition调用发现成员已归组必须拒绝。cron列举排除组成员，单路入口锁内最终复查，不能只有前端隐藏按钮。Y1旧未归组回执保留原hash/格式。

Y2c API/Owner/两个领取方向的竞争及重启回读验收，补前端可配置/禁入状态所需的明确产品入口。具体UI文件在读当前页面结构后登记；没有页面验收不把整体Y2称产品完成。之后Y3执行恢复、Y4生命周期、Y5十二源真实配置、Y6观察依序继续。

## 存储与字段

definition revision保存：scope、definition UUID、revision、prior ref、installation/generation、state(disabled/enabled/retired)、cron、relationshipPolicyRef、十二成员bindingRef及服务端解析的schedule/pipeline/control refs、actor、idempotencyKey/requestHash/contentHash、createdAt。Head仅current revision/ref/state/安装标识；成员索引关联当前definition+revision并独占scope/schedule。保存时固定public权威表；完整性约束验证hash、连续前驱、原binding FK和Head/current成员一致。RLS强制双租户、历史不可变；当前Head/索引允许原Owner在事务中CAS维护，不能变成无作用域seed。

## 验收与主库边界

先红后绿：配置完整十二路、默认停用、exact重放、版本冲突、成员重占拒绝；enable只对current controls/policy/权限通过，disable在源过期仍可安全停止；活动/未知运行阻止修改及retire；退役保留记录并释放索引；跨租户、临时表、角色撤销不允许写。并发领取与绑定用两连接真实锁验证。主库升级要先克隆完整演练；J原失败Run与Outbox继续保留，不改旧cutoff，不伪造恢复。

## Y2a 隔离验证结果（2026-09-16）

配置Owner/063已实现：默认disabled、版本CAS、原幂等请求回执、十二成员独占、完整组当前策略校验、可在源授权失效时停止、停用保留归属、确认无在途后退役、历史不可变与双租户RLS。执行身份executor与管理actor分开保存。新周期入口在调用原解析器前限制合法数值范围，拒绝超大范围、越界混合值、零步长。

Red：缺少Owner；旧测试安装仅满足FK但不满足原Composition模型验证；版本切换时current-member→head外键因外层SET CONSTRAINTS ALL IMMEDIATE过早检查。修复仅完善本文件测试夹具，通过原PostgresCompositionStore保存合法lock，并为当前成员FK命名，在Owner事务内明确延迟/校验该FK；未放松生产权限或外键。首次创建、enable/disable/retire全过程已通过。

最终完整隔离PG验证：test_pipeline_snapshot_schedule_definition_pg.py + test_pipeline_snapshot_schedule_claim_pg.py + test_pipeline_snapshot_schedule_recovery_pg.py，27 passed / 17.41秒，日志/tmp/aos-group-definition-final.log。覆盖角色撤销/viewer/未知actor、源拒绝后另一管理员停止且executor不变、active/unknown阻止编辑/退役、跨租户不可见、不可变历史、exact修改及旧回执重放、原领取与提交恢复。git diff --check通过。

范围限制：安装/签名资产和远程源仍为明确命名测试夹具，实际权限与配置持久化走真实PG；不能代替真实租户安装验收。尚无产品API/UI或成员领取围栏，因此063未部署主库且组配置不对外开放。下一波Y2b先建立领取围栏，再接API；Y2整体未完成。J原失败Run、历史Outbox、主库061保持原样。共享记录strong投影CURRENT，eventual异步项仍PENDING_ASYNC，不据此宣布业务完成。

## Y2b-1 领取围栏施工（基线7f6821f9）

先于API开放实施拒绝路径：pipeline_schedule_claim.py原schedule行锁下查询public当前成员；pipeline_snapshot_schedule_claim.py原十二schedule行锁下拒绝无definition的归组成员；qyh_cron_scheduler.py列举排除归组成员，但锁内检查仍为最后权威。此段不增加允许归组执行的旁路，definition exact执行授权在后续Y3绑定原领取回执实现后开放。未归组历史调度保持行为。新测试test_pipeline_snapshot_schedule_fence_pg.py用真实配置Owner建立归属，验证enabled/disabled、单路/旧group领取均拒绝，退役且显式重新enable后恢复未归组行为；cron列举测试证明仅排除归组成员。旧schema专用测试须装063依赖或显式创建相同归属表，不能用查询异常时忽略围栏。API/UI仍不开放。

Y2b-1复核新增pipeline_controlled_snapshot_ingress.py：ControlledScheduleExecution.claim_recovery使用独立Ingress事务，不能只在普通schedule_claim_connection防护。在原_guard_binding的current controls回调内、Run锁前锁schedule行，检查enabled及当前归属，整个实际恢复/输入事务持有锁；源组配置同一schedule行锁因此不能在恢复检查后插入。新增完整PG直接守卫用例。旧025专用schema行锁回归明确命名无组读取夹具，不作为063围栏验证；新完整PG用真实配置和归属读取覆盖新边界。

### Y2b-1验证结果

两个Red实际复现：enabled组成员可进入旧单路executor；受控Ingress恢复_guard_binding未拒绝组成员。已分别在原schedule行锁与原current-control事务守卫内查询public当前归属并拒绝；普通cron SQL排除成员，旧无definition组领取亦拒绝。受控Ingress同时检查schedule仍enabled；归组/停用与恢复在同一schedule锁上串行。新模块级读取函数统一原单路与旧组领取的权威查询，不捕获缺表异常、不降级放行。

最终完整隔离PG 33 passed / 20.75秒（/tmp/aos-group-fence-final-v2.log），覆盖enabled/disabled且旧flag被手工开启仍拒绝、无definition组领取拒绝且零运行、退役保持停用/显式启用后旧单路恢复、cron只执行未归组成员、原受控恢复守卫拒绝；累计包含Y2a配置及Y1跨连接恢复。旧025专用schema+执行/定时器回归74 passed / 8.12秒（/tmp/aos-group-fence-legacy-final-v2.log）。两个旧025夹具明确命名无组reader，仅验证旧行锁/绑定语义，不计为新归属安全证据；新完整库未替换该reader。git diff --check通过。

新增/修改文件以本提交为准，额外旧夹具test_controlled_schedule_guard_pg.py纳入。未改主库061、未重载真实host、未读取商城，未开放API。部署必须063先行，不允许先重载新代码到061。下一波Y2b-2正式配置API，之后Y2c页面和双向竞争；Y3才接带exact definition的组执行。当前安全拒绝不等于业务闭环已完成。

## Y2b-2 正式配置API（基线46c90d08）

新增aos_api/pipeline_snapshot_schedule_service.py与routers/pipeline_snapshot_schedules.py；在原pipeline_controls router.include_router注册/v1/pipelines/snapshot-schedules路径。原PipelineControlServiceFactory新增build_snapshot_schedule(scope)，组装同一当前controls与正式PostgresInstallationStore，API不构造替代authority。服务通过原runtime_worker_connection与consumer_connection、protected tables role gate，scope来自principal，不接受请求actor/tenant/凭据。configure请求为cron、policyRef、十二项scheduleId/bindingRef、expectedRef；服务加载每条最新binding并exact匹配，再交Y2a Owner。PUT /{definitionId}配置默认disabled；POST /{definitionId}/{enable|disable|retire}仅expectedRef；所有写操作Idempotency-Key必须唯一。GET /{definitionId}在原当前安装配置权限下返回精确ref/body，供提交未知后的只读核对；此阶段不增加重试或组执行按钮。

新接口严格JSON/64KiB、UUID规范、禁止额外字段，错误不泄露内部信息；借用原pipeline_controls请求体大小/异常映射惯例，避免import循环。配置读取复用原权限；UI清单与分页在Y2c明确后实现。HTTP命名service测试只验证路由/身份/错误，无业务成功宣称；完整PG service测试通过真实Owner和runtime连接边界验证写/读取/CAS/权限/双租户。迁移063前不重载主host。

Y2b-2复核：原factory的ManifestLoader构造会检查签名资产根目录存在；停用/退役/只读核对不能因该目录暂时不可用而失效。新增受限stop/read构造模式：factory仅在configure/enable构造源controls；stop/read模式Owner只持原CurrentConfigurationPermission，无源controls且强制拒绝configure/enable。该模式不跳过成员/安装markings权限，不允许传success，不允许激活。新增缺失资产根目录下停用服务可构造、启用服务拒绝，以及真实服务受限模式只可停用/读的验证。

### Y2b-2 验证结果

新增正式service/HTTP路由并挂入原router与factory。HTTP严格验证12 exact绑定/唯一成员/规范UUID/周期/未知字段/原Idempotency-Key，身份只来自principal，安全错误不泄密且不重试。实际服务使用原独立runtime连接、非超级用户/非表owner的角色门禁，原配置权限与Owner事务。跨连接配置/重放/启停/回读、陈旧绑定拒绝、负租户零记录、权限撤销后回读及重放拒绝、stop-only不能enable均经完整PG验证。

Red为新路由模块不存在；初次HTTP完整app测试因未指定18434误用默认5433连接拒绝，重新按隔离库命令执行，不计作产品失败或通过证据。最终累计81 passed / 35.35秒（/tmp/aos-group-api-final.log），包括HTTP/原管道API/factory/新service PG/配置Owner/组围栏。git diff --check通过。具名签名资产/源读取夹具仍不是真实租户运行；真实主库仍061/host旧版本，尚不对外开放新接口。

后续Y2c产品入口需先补当前配置列表、服务端可选exact成员与策略来源、按原key读取历史回执（只读确认未知提交，不能仅看latest覆盖旧结果），再实现页面。仍需双向并发验证，不以HTTP或81测试作为八工作台业务完成。Y3–Y6沿原清单继续。
