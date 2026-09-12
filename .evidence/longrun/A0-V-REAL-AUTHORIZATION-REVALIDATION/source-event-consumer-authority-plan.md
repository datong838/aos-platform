# 源事件持续消费：配置与事务接续合同

2026-09-12，基线ada282a4。承接商品源事件校验和原子批次登记；本文件是待实现方案，未新增读权限、DDL或生产消费者。

## 已核实的缺口

ScheduleBinding绑定policy revision/hash、operation、installation、generation、epoch、时间和批准状态，但没有source configuration exact ref、平台/店铺、对象类型、方法版本和源读取授权引用。EcomConsistencyStore可读已提交批次与投影进度，没有按该绑定给经营消费者提供权威事件读取的接口。不能从“角色能SELECT一张表”推断允许任意店铺/对象业务消费。

## 具体实现顺序

1. 为事件型策略增加受版本/hash保护的SourceSelection引用，绑定当前SourceConfig、QueryCapability、来源分级与允许对象集合；限定平台/店铺及方法版本。只继承已安装配置中批准范围，不允许HTTP传入SQL、表名或任意过滤器。配置缺失时返回缺少来源配置，禁止默认全店/全库。
2. 复用数据Owner读入口产生源事件行；只读取当前tenant/project/workspace、SourceSelection平台/店铺/对象类型、authoritative_store事件。事件完整性由核心包product_source_event验证，读Owner和能力合同承担身份与读取权限验证，SHA不能替代权限。
3. 消费选择以未存在同tenant/policy/sourceEventId的Occurrence为准；不能以MAX(input_revision)作为永久排除条件。按输入序号和outbox_id仅排序，每批最多100。不能把projected=true/false作为经营消费确认；其所有权属于原投影器。
4. 事件deadline必须由固定源发生时间、策略有效期和恢复窗口计算，重试不得now+TTL延长。晚到但已过业务窗口的事件保留明确missed/人工复核路径，不偷偷丢弃或执行。
5. 复用record_event_batch，同批Occurrence和Outbox原子提交。源选择与记录间再次校验源配置/策略版本；发生CAS漂移整批回滚。不同进程选择同一批依赖既有唯一ID/锁去重。Occurrence创建后崩溃可按存在性跳过，不需第二套业务Receipt。
6. 部署受监管生产worker：读取当前有效安装配置，先做Admission，再登记/claim/执行；禁用、generation替换、租户切换立即拒绝新动作；未知结果保持reconcile。只能调用既有Canonical Router/HostService，不直写Case/Run状态。
7. 空计划使用initial_store_analysis的既有Case类型，配置启用后由首次有效源事件起跑；WAITING_DATA恢复原Run；已有可靠画像时才进入最多三个候选的排序，不能把空计划等价于有数据。

## 文件与验证范围

- 配置合同、迁移与Owner：先在既有ScheduleBinding/策略权威合同上设计sourceSelectionRef的版本兼容，不直接修改不可变历史迁移。新增迁移具体编号在实现时按当前HEAD分配。
- 数据读取适配器：由既有数据Owner承接，不在工作台/UI或领域包内部直连数据库；核心包继续只做来源语义校验。
- 自动化执行器：复用automation_occurrence_store、automation_dispatcher和当前受治理生命周期，不启动绕过安装控制的常驻裸脚本。
- 实际PG测试：事务A先分配小序号但晚提交，B先提交并消费后，A仍可被发现；双写者不重复；发生策略/配置切换整批拒绝；跨tenant/店铺/对象/分级拒绝；过期事件不得变更deadline重试；崩溃后无漏项/重复副作用；禁用和卸载停止新Admission。
- 真实验收：源通道恢复且新配置/正式dispatch就绪后，以真实商品变化触发，记录同一Case/Run全链回执。测试构造事件不计真实链证据。

## 当前需外部信息的两个入口

1. 栖月汇SSH原身份认证曾返回Permission denied；需要此前成功连接的工具/配置路径或由用户恢复可用隧道。无需发送密码或私钥。
2. 固定九项正式调度登记的具体新增访问范围仍待答复，范围见dispatch-registration-access-review.md。不借高权限凭据、包装函数或fixture绕过已经发现的访问限制。

当前只有技术生命周期部分实证，首链与八业务场景均未完成。不push，230 L0挂起。后续施工必须沿本方案先补配置合同，不用临时开发者接线替代产品能力。
