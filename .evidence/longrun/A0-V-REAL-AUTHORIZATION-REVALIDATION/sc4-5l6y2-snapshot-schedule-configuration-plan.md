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
