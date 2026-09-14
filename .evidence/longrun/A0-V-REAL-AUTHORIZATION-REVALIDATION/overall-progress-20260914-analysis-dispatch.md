# 总进度：事件到分析承接接线截面

最终目标未完成，不按测试数/页面数折算百分比。

| 大阶段 | 当前判断 |
|---|---|
| AR2包拆分及平台接线 | 当前清册检查无错误；历史最终GREEN仍是fixture范围 |
| 安装/配置/禁入/恢复/重装 | 保留历史验证；新增源码与043迁移未部署主安装，需新候选和独立评审 |
| 真实更新自然触发Case/Run | 源码已串起生命周期消费、原事件proof、Occurrence/outbox/origin、精确领取、当前来源重验、installed分析命令和sealed Host承接。尚未实际在主安装创建Run |
| 首条经营闭环 | 正在补真实Host集成。黄埔0期销售武器包的有来源建议→exact评审→内容/能力→人工复核续跑→EffectReview/Wiki仍需同一真实链路贯穿 |
| 八工作台真实场景 | 待首链贯穿后逐场景扩展，不能以八页面可点算完成 |
| 连续观察/发布 | 尚未进入，发布决策未作 |

本轮新验证含真实隔离PG领取/回执/不可变来源、当前控制撤销拒绝及源码编排。Source/installed/部分Host用具名测试替身的地方均在各波证据中标明。下一步正式AnalysisHost的Run/Compilation/TaskRun/Receipt真实库集成；随后新候选评审安装，主库仍未应用039–043。不push，230 L0仍挂起。

后续真实Host验证发现：_start_lineage新Run后未调用编译Saga，缺CompilationReceipt，现有4通过1严格已知失败。新增analysis-start-compilation-bridge-design.md的CF1–CF6，当前进入CF1；这一发现是实际缺口，不是模型/SSH问题，不计首链完成。

CF1已完成exact桥接输入合同；CF2已实现当前配置职责及显式阶段引用读取，正在核对Logic/Skill与安装模板选择。CF3–CF6仍未完成；Run缺编译回执的真实PG已知失败仍保留。职责/阶段单测结果不折算业务完成率。

2026-09-14 CF2依赖链已补蓝图、当前职责/技能/Logic选择，CF3已完成兼容阶段模板与本任务Task/frozen v2 Brief准备。CF3-4修复公共Context冻结允许同租户跨任务/跨Brief证据错接：真实隔离PG先复现两项失败，修复后Context/Impact/Task准备14 passed，追加无Receipt断言Context6 passed。仍未解决启动证据/Eval与Context组合、Compilation/TaskRun连接；真实START严格xfail仍保留。上述代码未部署主安装，不折算经营闭环完成比例。

SC1：蓝图v2启动政策及Host拒绝错误用途已实现，44项回归通过。启动/经营证据分阶段方案已入原计划SC1–SC4；当前下一项SC2真实事件证据，其后SC3当前Eval/Context、SC4正式Saga/TaskRun。仍无主安装真实首链完成证据。

SC2：实现当前原事件启动Evidence存储并升级Task准备为真实PG Run验证；修复初始SQL状态hash与Python规范差异的误拒绝，保留历史记录。20 passed/1原严格xfail，新增写后撤销回滚启动证据8 passed；AR2 1896/174/93无错误。下一项SC3当前Eval/Context，SC4正式START与TaskRun仍未完成。

SC3-1：首阶段当前技能发布血缘派生Eval合同已实现；真实PG评测/发布/合同14测试通过（模型/安装依赖明确fixture）。回调中撤销/重复合同会回滚。下一SC3-2本任务Context冻结组合，之后SC4真实Compilation/TaskRun接入；首链未完成。

SC3-2：同一原事件事务内自动准备StageTemplate、Task/Brief、启动Evidence/Bundle、当前发布Eval与Context；累计29 passed，AR2 1898/176/93无错误。配置职责/安装依赖仍为明确fixture；尚未连接正式CompileSaga/TaskRun。下一波SC4，主安装真实首链、八场景及观察均未完成。

SC4-1：编译输入按当前蓝图组装三阶段Skill/职责/模板/本任务Context，41项累计回归通过；纯组装不授予执行权。下一SC4-2真实exact解析器与CompileSaga，随后TaskRun和sealed Host接入，首链仍未完成。

SC4-2：当前Context内真实Store exact解析与原CompileSaga已接，隔离PG可生成实际Plan/CompilationReceipt，累计37 passed，撤销和下游故障回滚。配置/模型/能力fixture边界保留；Plan仍需启动门，未创建实际TaskRun。下一SC4-3，主安装首链未完成。

SC4-3a：原生产启动门支持Host外层事务，9项累计回归通过，TaskRun/启动决定/Plan审批可随外层故障全部回滚。下一启动Preview/审批承接与实际TaskRun流程，然后接回正式事件START。主安装首链仍未完成。

SC4-3b：TaskRun可在首步未执行时保存真实初始输入检查点并暂停，15项累计回归通过，输入漂移拒绝恢复，不伪造画像完成。下一启动Preview/审批组合及sealed Host接线；首链与八场景尚未完成。

SC4-3c1：固定暂停初始化合同及完整授权方案入清单，33项累计回归通过；尚未启用新Action或执行规则。下一c2启动Preview、c3当前Action守卫、c4实际运行组合、SC4-4正式事件START。真实首链仍未贯穿。

SC4-3c2：初始化意图Evidence与冻结启动Preview完成，当前Agent/Skill版本漂移拒绝，累计34 passed，AR2 1901/179/93无错误。未批准Action/执行经营步骤。下一c3专用当前授权守卫、c4运行组合、SC4-4事件START；主租户首链/八场景/观察尚未完成。

SC4-3c3a：通用启动门拒绝初始化Action/初始化Preview误用，两项红测复现后19项回归通过；普通生产启动保留。尚未启用专用初始化授权。下一c3b当前授权及专用入口，再c4/SC4-4。

SC4-3c3b：当前初始化审批身份读取器完成，隔离库累计26 passed；不赋权、不生成审批。尚待接入当前来源/精确Task绑定及专用Action路径。AR2 1902/180/93，真实业务链仍未完成。

SC4-3c3c：当前原事件到编译/Preview/Evidence绑定守卫完成，累计33 passed；Plan变更、证据撤销、父审批撤销及原请求错接拒绝。下一专用Action连接与原子暂停；主租户首链、八场景、观察仍未完成。

SC4-3c3d：实际初始化Action草稿接入原Store，当前事务/身份/来源守卫已接，25项回归通过；保持R1不可执行，不新增审批。下一专用原子暂停门和授权承接整合，随后正式START及真实场景。

SC4-3c4：隔离库实际独立审批→原启动门→TaskRun→首步未执行检查点→暂停贯通，61项回归通过；通用启动/恢复/外部租约不能复用初始化授权。正式Logic发布检查已按实际权威修复。下一SC4-4正式事件入口和审批承接/当前续跑；主租户首链/八场景/观察仍未完成。

SC4-4a：当前已独立批准的来源策略可派生仅初始化许可，不新增人工审批、不冒充批准草稿；实际初始暂停和权威Evidence回读通过，累计40 passed。人工拒绝/来源失效不可绕过。下一正式事件入口自动接线，首链仍未完成。

SC4-4b1：共享原Run创建与原时间稳定重放完成，29 passed/1既有xfail。下一正式事件服务串接完整准备与初始化、原Host绑定；完整START尚待验证。

SC4-4b2：正式事件handle自动初始化到实际暂停TaskRun和Host Receipt已通过；82项回归全过，AR2 1904/183/93无错误。修复完整10操作分派锁与分析journal摘要口径，原raw Host缺编译改为明确拒绝测试。主安装未迁移/部署，真实首链仍未完成。下一SC4-5当前数据/经营续跑承接，随后新包安装、真实首链、八场景和观察。

SC4-5a：原正式初始化链经当前sealed data Host创建真实待数据需求和WAITING_DATA，TaskRun保持暂停；53项回归通过，AR2 1905/184/93无错误。修复数据Host重复响应与不可变journal冲突。显式数据政策仍待安装内自动计算，主租户未运行，下一SC4-5b恢复前置权威与专用续跑。

SC4-5b：原START Receipt可组合实际WAITING_DATA/Requirement作为恢复前置，无需伪造中间回执；63项回归通过，无真实Fulfillment仍拒绝。下一SC4-5c经营事实执行上下文与专用当前恢复门，再自动政策/真实补齐；首链未完成。

SC4-5c1：实际事件accepted后通过完成attempt+原Receipt验证历史Occurrence引用，修复status变化误拒绝；51项回归通过，篡改完成回执/元数据拒绝。下一c2已完成原事件当前来源上下文，再专用恢复门与真实Worker，主首链未完成。

SC4-5c2：完成事件当前来源上下文已接，29项回归通过；不构造旧Claim，漂移/异步回调拒绝。AR2 1906/185/93无错误。下一完成事件数据需求连接与专用恢复，之后自动政策/真实补齐/业务Worker；主首链未完成。

SC4-5c2b：完成事件可首次创建或重放同一数据需求，不依赖旧Claim，34项回归通过；来源/数据政策自动化仍待后续。下一专用当前恢复门与真实数据/Worker承接；主首链与八场景未完成。

SC4-5c3a：完成事件中原启动/动作/编译/初始化Evidence和当前身份核验完成；来源派生与实际独立审批来源均有隔离PG验证，27项回归通过，AR2 1907/186/93无错误。下一专用当前数据恢复组合；主首链未完成。

SC4-5c3b：专用当前数据恢复Session与原Task/BusinessRun组合已接，55项回归通过；真实缺Fulfillment仍拒绝，正向状态组合的数据与dispatch明确fixture，未作完整恢复成功声明。AR2 1908/187/93无错误。下一真实数据可用性核对、自动需求消费与完整补齐，再真实Worker/安装/八场景。

SC4-5d0：主租户只读数据差距已核实：Shop1/Product57有效，2/12物化种类、两条调度关闭，需求/补齐/观察/Readiness/Query回执均0，主库a0v_038。已按自动政策→12类受控采集→Outbox真实补齐→完整恢复/Worker→主安装业务观察重排执行顺序。首链与八场景未完成；下一安装内数据政策与自动请求承接。详见analysis-real-data-gap-verification.md。

SC4-5d1：自动首装需求入口已接现有安装配置与预算权威，原事件前30天/全事实/稳定重放；40项回归通过。配置预算在自动组合测试中明确fixture，主租户未运行。下一现有事件Worker连接自动需求及失败重试，再12类受控采集和Outbox实际补齐。

SC4-5d2：生产事件Worker已固定连接自动需求，START+DataRequirement原子提交；40项回归通过（零Run首次、已有START补接、重放、失败全回滚）。来源/配置fixture未计主租户完成。下一12类受控映射采集、Outbox实际补齐，再恢复/Worker全链及八场景。

SC4-5e1：SKU全状态快照1.6.0候选已生成，11项静态回归通过；源1.5.0不变，新树891b9312ecd040d19388e624fc40d636f08e2c567e56487650283a38aab6b0c6。修正旧sku_no映射以符合原barcode契约，关联尚未物化，未构建签名/发布安装，主库仍2/12。下一剩余9类（分类/订单优先）及时间/关联语义，再实际补齐。

SC4-5e2：显式观察时间v3纯映射已实现，84项回归通过；无源修改时间时保留观察版本与明确未知标记，不推断缺失删除，旧v1/v2兼容。AR2 1909/187/93无错误。尚无主安装/真实补齐；下一分类候选和层级检查、订单显式软删观察口径。

SC4-5e3：分类观察快照/完整父子图约束已接入1.7.0静态候选，94项回归通过；新树5641f4890a2198fd92d6eefc4e68400d90ce7030c8e8e8059a657c09de4ba069。静态声明4/12，主库仍2/12；关系和真实补齐未完成。下一订单显式软删观察快照，再其余7类和完整首链。

SC4-5e4：订单观察快照1.8.0候选完成，保留关闭订单、真实创建时间和金额，显式删除标志严格验证；100项回归通过。源库只读核实12类结构与数量，订单185/明细235；明细创建时间全0，后续必须通过真实父订单关联解释窗口。静态映射5/12，主库仍先前核实2/12，未发布安装或真实Fulfillment。下一订单明细及剩余6类、真实关联/补齐，再恢复与八场景。

SC4-5e5：订单明细1.9.0静态候选完成，37项针对性回归通过，六类静态评估通过；create_time=0保持未知，经营窗口与三类关系待真实Owner。新树b52f6a76334528d7c8cde06e802252e6934dd4ead29c35219f976d3f55413e01；静态6/12、主库仍先前核实2/12。下一物流隐私遮罩契约及剩余映射，再关联/实际补齐/完整首链。

SC4-5e6：物流完全遮罩快照1.10.0完成，37项回归通过，七类静态评估通过。物流号不读取并标为完全遮罩，姓名/轨迹排除，零发货时间拒绝而不伪造。树d17d81fefde3e8159c1c18b8a361f6bdac128350c1623b9181540d06d57558cb；静态7/12，主库仍先前2/12。下一CustomerLite最小公开快照与后4类显式源政策，再关联/补齐/主首链。

SC4-5e7a：v3公开属性投影与对象schema版本前置完成，105项回归通过；观察来源四标记强制保留、状态不可隐藏。真实只读聚合会员54/54注册时间有效，物流19/19发货时间有效。CustomerLite候选继续，主首链未完成。

SC4-5e7b：CustomerLite公开schema2候选1.11.0完成，45项回归/八类静态对象通过。仅选原允许六列，未知status拒绝，显式软删与真实注册时间保留；公开业务属性仅等级/状态/注册时间加强制来源标记。新树f2bc7069f564af79dbef3feb14da9ba64a7b6fd767cef4a2879421caf71cb7f5；静态8/12，主库仍先前2/12。下一后四类源字段政策、关系/支付订单关联与真实补齐。

SC4-5e8：后四类源结构/隐私声明及三类最小快照1.12.0完成，65项回归通过，十一类静态对象通过。新树7d0eaeb6c99da59f8e9f08f78607da60320f97bdaab881184c4f7e6a47fd9587；配置仅元数据、评价仅评分/关联键，敏感正文未读。支付211条relate命中但交易号仅181对应，仍未完成，下一查源业务事件/订单副交易号语义。静态11/12，主库仍先前2/12，完整补齐/首链未完成。

SC4-5e9a：源判别列conditional_only精确范围约束完成，82项回归通过，其他业务事件行物化拒绝。真实支付拆分203普通订单+8会员卡；普通94关闭中22旧交易号不同，父订单/会员无错配。下一普通订单Payment快照候选，仍不声称关系Receipt或主首链完成。

SC4-5e9b：普通订单支付1.13.0候选完成，75项回归通过，十二类静态规范对象通过。树07478676ef5be20e10d185fe98113932a16a0b41d973248729285eaf4879015b；仅203普通订单支付范围，排除8会员卡，历史关闭重试保留。静态12/12≠主采集12/12；主库仍先前2/12，实际关系/完整补齐/首链/八场景未完成。下一复用受控快照入口落实完整批次与跨对象关系，再Outbox/Fulfillment/恢复。

SC4-5f1：同事务源集合读取原语完成，56项回归通过；真实12类私有InnoDB可重复读1.41秒完成，11类规范转换通过、支付203条失败。已定位relate_id实际str而旧映射int，所有行同因；金额非负、必填无缺。下一严格数字字符串关联键及新支付候选修复，然后再次真实整组验证；主数据与Fulfillment未写。

SC4-5f2：relate_id真实字符串类型修复完成，v3规范正整数字符串校验；122项三版回归/59项候选回归通过。1.14.0树9cb6cd266571dfbe7725e3411229f307025beec6ea93380a995529aa610d4b76。真实同事务十二类892条全部规范转换通过（含203普通支付），约1.52秒；仅开发者只读验证，主落库/关系/Fulfillment仍未完成。下一完整集合的关系/窗口与正式Owner回执绑定，再Outbox恢复和八场景。

SC4-5f3：当前快照组Owner边界完成，14项单元/隔离PG验证通过。固定顺序嵌套原控制/选择Owner、同租户安装包连接约束、共同窗口/最小限额、执行后完整复验；PG中途控制更新导致外层回滚。签名资产fixture未计主安装通过。下一组认领与持久化输入/共同观察证据，再关系质量与Fulfillment；主首链未完成。

SC4-5f4a：a0v_045组认领/成员/输入不可变表与延迟完整性约束完成，25项隔离PG/原Ingress回归通过。拒绝缺成员、重复归组、错actor/hash、异常输入manifest、跨租户及历史改写；主库未执行迁移。下一应用Owner原子组认领与重放，再同事务输入保存/正式补齐。

SC4-5f4b：组认领Owner完成，41项隔离PG回归通过；两成员原认领+组日志原子创建/精确重放/旧认领拒绝。审查新增捕获异常后提交反例，先红后以保存点修复半组残留；原外层事务所有权保留。下一同事务一次读与组输入持久化/未知结果核对，再真实关系及补齐；主首链未完成。


SC4-5f4c：当前配置绑定组读取完成。新增pipeline_selected_snapshot_group.py，当前sourceConfigurationRef/direct状态严格核验，私有连接一次整组读取，原成员最严格界限不可放宽。52项测试通过（3.86秒），AR2 ar2-7扫描1913模块、五类错误为空，memory revision AOS-000573 GREEN。测试中的权限/连接均明确替身；本波无真实源调用，无主库迁移/对象写入/Fulfillment。下一项：组认领提交确认后，真实原输入与manifest原子保存、精确重放与未知结果禁止重读。


SC4-5f4d：ControlledSnapshotGroupIngress完成，原组认领独立提交确认后一次读取，全部原ControlledIngressJournal输入和真实哈希manifest同事务保存。47项隔离PG组合测试通过（14.19秒），含新增13项、旧单表、组认领与schema；AR2扫描1914模块五类错误为空。失败/取消/读后禁入/第二输入失败整组回滚，认领保留且不重读；输入commit成功但ack丢失能完整零源重放。无对象apply/运行完成/Fulfillment，无主库迁移或真实源调用。本波fixture不是主真实安装验收。下一项：对同批对象开展关系/软删/业务窗口的方案与实际字段差异核对，采用包内声明与通用校验落实，不沿用未核验旧link别名。


SC4-5g1：同批真实关系审计完成。15测试通过（4.55秒）；真实09:07:08.053263Z–09:07:09.575589Z同一InnoDB只读事务12类型，统计保存real-relationship-audit-20260914.json。235明细/203普通支付/19发货均匹配父订单；订单号和memberId交叉字段235/203/19无不一致。235明细自身时间均未知，但父订单创建时间均可用；其中69关联软删订单。32订单、1评价缺少当前范围客户，不得客户质量宣绿。65商品分类当前诊断解析拒绝，原源Goods.php:2120–2121使用前后逗号封装，下一波核实/严格支持该格式。源schema实际有weapp_id但P05未映射，后续候选需按原schema/masking补齐，不能推算或读取weapp_openid。
正式关系写入/客户修复/窗口读模型/Fulfillment仍未完成；不跨店扩读、不补造客户、不以重复统计充当推进。下一项：分类分隔格式严格解析修正及对应真实重验，再包内关系声明及P05关联字段候选。


SC4-5g2：分类源逗号格式严格支持、Order关联键候选1.15.0完成。新树b09e20811f08b3d40e155406dd293d2642779acb6caed9ec8272f8337655779c；源1.14树不变，仅bundle/P05/masking/evals四文件改变。weapp_id与out_trade_no依实际结构证据增补，openid排除加固。33测试通过4.47秒，分类/Weapp首红2失败22通过后修正。新候选十二类静态评估通过，未发布安装。
真实09:15:33.754126Z–09:15:35.178481Z同事务重验：65商品92分类引用全匹配，185订单Weapp全匹配；203普通支付181当前trade相同22不同，关系仍按原orderId，未错误删除历史支付。客户32订单/1评价缺失不变，软删端点不等于当前活跃关系。源行不持久化、不写主对象/Fulfillment。证据real-relationship-audit-20260914-order-keys.json保留此前失败审计。下一项：包内关系声明与通用有界物化，显式质量/软删边界，再接正式组输入Owner。


SC4-5g3：通用SnapshotRelationshipPolicy编译及有界assessment完成，不含Niushop业务字段硬编码。只输出两端真实未软删的candidate link，missingReference/invalidReference/missingParent/deletedEndpoint/allowedUnset分别计数，不补对象、不推断删除、不授予Readiness。严格1..12对象、1..32规则、每类<1000、每引用<=32、总候选<=24000；canonical policy hash重验防dataclass绕过。77项组合测试通过4.25秒（新30+原核心模型+既有诊断）；哈希伪造反例先1失败29通过，修复后全通过。AR2扫描1915模块五类错误为空。下一项：不可变领域包14条规则声明及实际同批核验，再接原组输入/应用Owner与质量门。


SC4-5g4：领域包1.16.0十四关系声明完成，树be89c813a9185c05a4c923016977f8ac09df387c78c059ef10bfc800083e9c93；源1.15保持，仅bundle/evals变更新增原policies导出目录snapshot-relationships.v1.json。策略hash e5ca449b179b17e3ee7c24f657dab3393a57c1111dbcded2246c91b805c3b366。34测试通过4.40秒，12对象+14规范关系静态评估通过；每个引用字段核对实际映射公开输出，旧goodsId别名反例拒绝。
真实09:29:16.419390Z–09:29:17.966551Z同事务12类：通用策略核验1162条两端未软删候选关系，全部原_normalize_rows规范通过；missingReference/invalidReference全0；客户缺父33（32订单+1评价），软删端点独立报告；不推断删除或补造对象，主关系写入0、formalFulfillment=false。证据real-relationship-policy-20260914.json只存数量/哈希。下一项：当前包策略资产与原组输入manifest绑定、持久化关系准备，再按原Owner应用与质量/Fulfillment接通。


SC4-5g5：PipelineSnapshotGroupPolicyOwner完成，全部当前控制内按原installation/artifacts/release policy验证同包导出JSON exact ref、文件字节哈希、公开字段及完整对象集合；执行后再查策略再由GroupOwner复验控制。59组合测试通过3.89秒，补public projection隐匿反例后新文件16项通过3.47秒（合计覆盖60项）；AR2扫描1916五类错误空，AOS-000573 validate GREEN。测试安装/签名资产为明确doubles，不宣称主真实发行资格通过。本波无源调用或业务写入。下一项：只读消费已持久化组原输入，绑定manifest/规则hash和原时间后生成关系assessment，缺input不主动读取源，再关系持久化与原应用Owner。


SC4-5g6：PipelineSnapshotGroupInputOwner完成。只消费已有原组claim+input，在全部原当前控制内核对manifest/request/逐原journal与rowCount/对象类型/原观察窗口；前后重新加载比较，callback改动或禁入均拒绝，缺输入不隐式采集。33组合测试通过13.37秒；再增越窗保存反例后新文件12测试通过7.68秒（共34覆盖）。AR2扫描1917模块五类错误为空。无真实源调用或主数据/安装变更。下一项：同事务组合当前策略和原输入，输出带manifest/精确policy双hash的关系核验，再关系准备持久化及原应用Owner。


SC4-5g7：PipelineSnapshotGroupAssessmentOwner同事务组合完成，从原input取得唯一完整对象组，原policyOwner核验精确包策略后assess；assessment payload/hash绑定租户/group/claimRequest/manifest/精确policy/策略hash/源时间/counts/候选关系。consumer后重算hash且两原Owner再验，修改counts/links/input/发行否决均拒绝；无采集或apply。35组合测试通过10.98秒。首次夹具将Shop改Weapp但沿用旧SourceSelection规格被原RuntimeConflict正确拒绝；夹具改为通过原approve/append创建新精确mapping hash与控制版本，产品门禁没有放宽。下一项：同回调原事务不可变关系准备journal，再原对象/关系应用与业务质量/Fulfillment。


# 不可变关系准备 journal 验证

SC4-5g8：a0v046 隔离 schema 与 PipelineSnapshotGroupRelationshipJournal 完成。原 input exact manifest 外键、严格 payload/时间/策略绑定、counts/link 形状、8 MiB 界限、tenant RLS FORCE 与不可变历史；准备在原 AssessmentOwner 同步回调及保存点内，原事务提交由调用方确认。

48 项隔离 PG 组合测试通过，20.84 秒。首次迁移 SQL JSON 常量被 SQLAlchemy 识别为参数，改为 jsonb_build_object 后完整 head 迁移及测试通过。格式合法但虚假 counts 的记录，当前 Owner 重算后拒绝；外层回滚、捕获后置发行否决均无准备残留，精确重放不增加源调用。

AR2 ar2-7 扫描 1919 模块，五类错误为空。主库仍未迁移，关系未应用，无正式 Fulfillment。代码 head 为 a0v046，主库此前确认 a0v038 未改。来源发行资产仍为测试 fixture；准备记录不能当已应用 Receipt。

下一项：独立提交确认后按原 ConsistencyStore 应用原对象批次与关系，验证 Receipt 完整性、忽略项、失败恢复和旧关系处理，再接业务 Readiness。


# 组对象原链路应用验证

SC4-5h1：ControlledSnapshotGroupObjectExecutor 完成。先独立提交关系准备并确认退出，再按原控制顺序调用 ControlledSnapshotExecutor.resume_saved，复用真实 ConsistencyStore、派生准备、Projector 与 dataset Receipt。阶段间复验整组当前准备，最后逐原 command 重核当前权威对象、outbox 和投影，全部 pending=0 才返回对象阶段完成。

9 项完整 PostgreSQL 回归通过，14.95 秒（新 5 项和原单表 4 项）。Shop+Weapp 两成员产生 2 份权威对象/Receipt/投影对象/数据集/历史记录，运行仍 running，关系写入 0。第一次成员完成后中断可重放首成员并续跑第二，源调用保持一次；准备 commit ack 丢失不开始应用。历史数据集成功但权威对象已被原 Store 更新时，最终拒绝旧组结果。

AR2 扫描 1920 模块，五类错误为空。测试表为完整隔离 PG schema，源和发行资产仍是明确 fixture；主数据/安装未改变。对象阶段是逐成员可恢复提交，不声称整组对象原子事务，也不宣告整组 Readiness 或 Fulfillment。

下一项：严格关系写入模式，拒绝悬挂或被新版本覆盖的关系，保留原通用写入行为；随后固定关系命令准备、提交确认、实际应用及 Receipt/投影核验。

### SC4-5h2 严格关系应用验证

原 EcomConsistencyStore 增加 apply_strict_link_batch 非空纯关系入口，共用原事务、租户、幂等、CAS、Receipt/outbox；原 apply_batch 行为及 BatchCommand 序列化不变。严格模式在事务内锁住端点及已有关系，提交前和重放时均以原 _reconcile_base_events 核对当前关系与唯一权威事件。缺端点、被新版本替代及旧宽松忽略 Receipt 均拒绝；任意失败整批回滚。相同内容已有关系和显式 tombstone 可通过，未加入自动删除推断。

新增8项SQLite反例先红后绿；62项组合回归通过20.21秒，包括完整Store51项、组对象7项、原单表4项。新增隔离PG直接消费组候选证明严格写入/重放和混合缺端点回滚；并发连接100ms lock_timeout 在新提交和重放核验时均拒绝端点更新，原事务退出才释放锁。源调用始终一次。AR2扫描1920/分类187/迁移93，五类错误为空。

主库未迁移、真实关系未写入。当前严格入口是原Store一致性能力，不是绕过整组当前权限的授权入口。下一波：持久化精确关系 BatchCommand，绑定已有组准备及固定检查点，独立提交确认后才可严格应用；再接原投影和业务质量核验。旧关系清退及32+1客户引用缺口仍未解决，整组Readiness/Fulfillment未完成。

### SC4-5h3 关系命令准备验证

新增 a0v047 及 PipelineSnapshotGroupLinkCommandJournal。仅从原 current assessment 生成纯关系命令，先重核所有原对象投影及原不可变关系准备；服务端 stream 使用 installation_id 和 policy path，幂等键绑定 group/assessment。完整命令及 CAS 检查点不可变保存，后续重放不再读检查点重建；空组保存明确null，不造 Receipt。

35项隔离PG组合通过49.96秒，其中新13项，原关系journal15项，组对象7项。验证原命令应用后检查点已前进仍精确重放；原准备缺失、未应用对象、权限撤销、回滚、租户隔离及不可变约束；保存后禁入即使外层捕获仍由savepoint清除；形状和hash合法但候选关系被改的记录被当前Owner拒绝；真实空输入无权威Receipt。首次实现把安装引用误按普通resource_id读取，按原CurrentInstallationRef.installation_id纠正，没有修改引用协议。

AR2扫描1921/187/93、五类错误为空。迁移只运行隔离库，主库仍原基线，真实1162候选未应用。本波准备不是应用授权或Fulfillment。下一项：独立提交确认后重新进入当前Owner，严格关系应用；复用原有精确事件投影流程而非全租户扫队列，最终重新核对完整对象及关系当前Receipt/投影。旧关系清退、客户引用缺口、业务Readiness仍待完成。

### SC4-5h4 原关系执行与精确投影验证

ControlledSnapshotGroupLinkExecutor 已接通原对象恢复、已提交命令准备、严格Store应用、原精确权威事件投影及最终当前核验。原 pipeline_controlled_projection 提取内部共用函数，保留单表父输入和派生校验/5000上限；组仅投影当前命令的<=24000事件，沿用tenant顺序锁/hash/前序阻塞/原Projector，未改全租户worker。

20项组合通过39.48秒（新7项、原精确投影9项、原单表4项）；增加返回relationship_scope=current_candidates_only后完整成功重放单例再通过10.86秒。真实隔离PG证明两对象+一关系仅3个原Receipt，图边一次，schedule仍running；准备commit ack丢失不apply；关系已commit但ack丢失保留原Receipt后续重放；图写入后异常回滚图边及投影标记；阶段间撤权无关系写入；更早无关事件阻塞、更晚无关事件保持pending，均不越界消费。源调用始终一次。

AR2扫描1922/187/93、五类错误为空。主部署/数据库未改变，测试源与发行资产仍fixture。该结果严格限定本轮candidate关系，不表示旧关系已清退、客户引用齐全、业务Readiness或Fulfillment。

下一波：补齐历史关系残留核验。当前事实是引用改向可能新增关系而旧边仍在；先以原当前输入、包规则、已提交候选命令和原Store核验出残留/缺失/不确定范围，禁止凭快照缺行推导删除。随后显式关系清退方案/策略和恢复，再接完整Readiness与正式Fulfillment。

### SC4-5h5 当前已出现行关系残留核验验证

新增原Store有界 read_active_links_for_rows，强制exact scope/明确非空行集合、双端tenant/shop、<=32规则/<1000 IDs、最多24000活跃关系，空集合绝不扩大查询。新增PipelineSnapshotGroupRelationshipAudit，原当前命令/全部对象及候选投影核验后，按包rowType/direction只查本次出现行，比较规范candidate identities；旧关系仅列发现，未删除。引用缺失/非法/父对象缺失及比本次source观察更晚的额外关系列为unresolvedExtras；完整引用且非更新关系列为cleanupCandidates，但尚无删除执行或策略授权。前后有界读取比较且回调hash/current Owner复核。

58项组合测试通过35.78秒（Store51+新PG7）；新增缺父引用场景首次测试误解析empty parent的null command，修正夹具筛选后单例通过8.21秒，当前新PG覆盖8项。真实隔离库验证正确边无残留；旧父边只报告不删；未出现子行和tombstone边排除；新于快照的关系保留不确定；父对象缺失时额外边不得被列为清退；回调篡改/撤权拒绝、跨workspace/shop空结果、超界拒绝。源调用均一次。

AR2扫描1923/187/93五类错误为空，AOS-000573 memory-validate GREEN。主库和真实关系未改。当前发现不等于业务质量绿色。下一波：在领域包规则中明确选择性启用present-row清退语义，旧v1保持候选关系语义；随后固定原残留payload的清退命令及原严格Store/投影恢复，禁止缺行推断和清退较新关系。

### SC4-5h6 显式清退策略候选验证

关系策略v2增加固定present-rows-only retirement约束：引用完整、拒绝晚于观察关系、禁止缺行删除；v1 retirement_mode默认disabled，原候选生成行为不变，模式纳入原完整hash且assess重新编译核对。当前PolicyOwner继续exact artifact/current release/public fields检查，v2不绕过原资格。

56项策略/Owner单测通过4.97秒；原关系执行+残留核验15项隔离PG回归通过77.48秒。新策略本身不生成tombstone。候选1.17.0相对1.16.0仅版本/策略/evals三文件变化，12映射逐字不变；静态14canonical关系、公开字段、缺客户/软删除可见性通过。对象mapping旧评估明确继承未重跑，不宣称新12类真实应用。

候选tree sha256:9cb8cd7c54fee2dd1f9e490b0d9f6e735045002f4b5d3164d6c1cd7ce83f89d3，policy sha256:03cd5157f54ed2c7156d82bf4903cff96c2c83459ce3e91b4637cdf59ee86ae6。未重建OCI镜像/签名/发布/安装，未删除真实关系。AR2扫描1923/187/93五类错误为空。

下一波：原Store增加显式tombstone的旧payload前置校验，必须在同事务持有端点/关系锁时比较准备时hash，避免清退覆盖期间更新；原Receipt成功重放校验自己的当前tombstone不再要求旧hash。随后在v2当前包策略门内固定残留清退命令、提交确认、原严格应用及精确投影。32+1客户引用缺口、正式Readiness/Fulfillment、真实首链和八场景仍待完成。

### SC4-5h7 条件清退原语验证

原Store新增apply_strict_link_retirement_batch，命令tombstone属性绑定retirementExpectedPayloadHash；持有原端点/关系锁后，所有旧边必须仍活跃且hash相同才写入。Receipt.result额外retirementPreconditionChecked绑定完整requestHash，普通删除Receipt没有此证据不能重放为条件清退；自身成功重放核对当前tombstone和权威事件，旧hash不再与已经替换的记录比较。BatchCommand/BatchResult模型和其他入口不变。

59项Store回归通过4.99秒；10项隔离PG关系核验通过（前一组合69项中唯一失败在新增单测夹具，PG10全部通过）。首次混合清退夹具给第二商品构造倒退checkpoint，被原Store正确拒绝；修正夹具时间后全Store通过，未改checkpoint规则。验证旧payload变化整批拒绝，无部分tombstone/Receipt/检查点推进；纯tombstone及哈希必需、同幂等键修改旧hash冲突；PG旧父边精确清退后正确边仍活跃，期间更新则旧边保留且无新Receipt。

AR2扫描1923/187/93五类错误为空。主数据未清退，实际策略/当前组授权仍需后继Owner。下一波：a0v048不可变清退准备，绑定当前v2包策略、原命令、原残留audit和固定旧hash/观察时间；支持已应用后旧边消失时以原条件清退Receipt回读恢复，不能重新猜旧边或生成新命令。随后原精确投影和最终残留复核。

### SC4-5h8 不可变清退准备验证

a0v048及PipelineSnapshotGroupRetirementJournal完成。新prepare须当前v2显式策略、原组input/候选命令和对象/候选投影合格，在原Audit回调保存exact audit、父commandHash、DB观察时间、完整条件tombstone与preparationHash；FK/SQL绑定、FORCE RLS、SELECT/INSERT only和不可变历史。每条清退重新验证原已出现行/规则完整引用、非wanted关系、旧时间不晚于原source，命令属性绑定manifest/assessment/audit/旧payload。

Store新增只读read_committed_link_retirement。清退前重放要求原Audit未变；清退已成功后按原Receipt的前置校验标记、当前tombstone和权威事件核验，不因旧边消失重造命令/检查点。空残留保存null，不造Receipt。已应用回读仍核当前v2及原行范围，不能删除wanted边。

61项Store回归通过4.76秒；14项完整隔离PG清退准备测试通过87.05秒。覆盖原命令清退后精确重放、缺记录read不写、回滚和后置撤权savepoint、旧边变更、普通删除Receipt冒充拒绝、v1拒绝、空残留、tenant/不可变、FK/assessment/count/active/time五类数据库反例，以及形状/hash合法但改成当前wanted边的准备被原Owner拒绝。

AR2扫描1924/187/93五类错误为空。主库仍未执行048或其他待升级迁移，主业务没有清退。下一波：独立提交确认后执行原条件清退及精确投影，验证commit ack丢失/图写入失败/撤权恢复；最后再次做完整关系残留核验，明确尚存数据缺口，再接业务Readiness/Fulfillment。

### SC4-5h9 条件清退执行与最终核验验证

ControlledSnapshotGroupRetirementExecutor接通原候选组执行、已提交清退准备、原条件Store、精确清退事件投影及最终残留Audit。每阶段重新核当前原准备，Store提交后故障保留原Receipt恢复；仅current_present_rows范围，仍有missing/extra/unknown返回requires_attention，不创建Readiness/Fulfillment或完成schedule。

5项完整隔离PG恢复测试通过88.63秒；再补较新残留/空清退2项通过39.84秒（共7覆盖）。夹具旧父关系先由原Projector投影为历史状态，之后仅旧边从权威活跃集与graph清退，正确边保留；最终5个Receipt无重复、源始终一次。准备ack丢失不执行，清退ack丢失凭原条件Receipt恢复，图删除异常回滚图和标记，阶段撤权停止。较新额外边保留并返回requires_attention，未被本组消费的更新事件仍pending；空清退不增加Receipt。

AR2扫描1925/187/93五类错误为空。主系统数据/安装仍未改变；这只是完整隔离原Owner链路的代码验证，未冒称真实经营首链完成。下一波回到真实数据质量：只读核查现有32笔订单+1条评价客户引用缺口的实际来源，区分注册站点不一致、源记录不存在、软删除等事实，输出不含客户标识的计数与证据，随后决定领域包参与客户范围与业务Readiness要求，不能盲目扩大商户范围或伪造客户。

### SC4-5i1 真实客户引用缺口核验结果

2026-09-14 19:26:04—19:26:06（北京时间），当前P02商城私有配置、独占Jdbc、同一InnoDB REPEATABLE READ READ ONLY事务聚合2.02秒。仅parent.site_id=1关联ns_member主键，未导出客户标识或字段，无业务写入。真实源连接正常。

未删除Order125条：98条客户在同site，27条客户在当前ns_member全表中不存在，涉及3个不同引用。已删除Order60条：55条客户同site，5条客户不存在，涉及2个不同引用。ProductReview5条：4条同site客户，1条客户不存在。所有分组跨site匹配/非法引用/未知site/客户删除标记/禁用匹配数均0。分组distinct可能重叠，不相加推断全局不同客户数。当前事实不能证明客户为何不存在，不称已物理删除或恢复过源数据。

185=125+60、32=27+5和Review缺口1与此前关系assessment精确对账。结论：不能把问题归因SSH或P08 site过滤；保持P08现有范围，不扩大站点读取，不伪造CustomerLite。订单经营事实仍真实存在，不应为关联缺口删掉27条有效订单。缺口须按业务用途披露/约束：全店汇总与商品经营分析可保留其订单事实并标注客户关联未知；客户分群/客户动作不能将未知关联计作可定向客户。该处仅确定后续方案方向，没有放宽正式Readiness门禁。

现有source-quality.v1.json只声明元数据可观察质量，不包含行级关系用途规则，因此下一波先补显式用途质量方案与包策略，再从原组质量证据接实际Readiness/Fulfillment；不能用pipeline成功代替业务数据完整。主库/安装未变，无正式Fulfillment。AR2继续按ar2-7核验；脚本输出存在时在任何源调用前拒绝，避免重复诊断覆盖原证据。

### SC4-5i2 用途关系质量计量验证

新增 pipeline_snapshot_relationship_quality.py：策略exact绑定原关系policyHash，逐用途完整列出required/disclose，禁止漏项/重复/未知/全disclose；执行时重编译防篡改。复用原完整cohort/key/重复/容量/关系策略检查。每规则observed=excluded+eligible，仅显式删除行排除；活跃行缺客户仍保留分母。多个引用全部存在且父未删除才complete，allowUnset单列；缺失/非法/删除按行计数并仅一次incomplete。返回用途所需缺口、应披露缺口、空分母规则，不产生ready/Fulfillment或改旧阈值。

Red先确认模块不存在；18项新增测试5.20秒通过；连同原关系和正式DataRequirement质量测试共82项4.85秒通过（8个既有运行警告）。订单185/有效125/客户完整98/缺27是基于已核验聚合计数构造的测试，不冒充再次源读。AR2 ar2-7扫描1926/187/93，五类错误为空。无源连接、数据库、安装或业务副作用；主库仍未升级。保护9月13日进度用户改动。

下一波SC4-5i3：从冻结1.17生成1.18候选，新增声明式用途关系质量策略及静态执行评测。initial_store_analysis对Order.placedByLite与ProductReview.byMember披露但不剔除事实，其他12关系必需；customer_cohort_analysis要求全部14关系，不代表该业务Profile已注册或允许动作。旧1.17、12映射、原source-quality元数据策略与首装DataRequirement保持不变；没有签名安装/正式就绪资格。随后SC4-5i4从当前包Owner绑定该导出策略和原快照，避免外部自报计数。

### SC4-5i3 Niushop 1.18用途质量候选验证

新1.18基于冻结1.17（sha256:9cb8cd7c54fee2dd1f9e490b0d9f6e735045002f4b5d3164d6c1cd7ce83f89d3），目标树sha256:5f3c6c00002c184429ceaaeca626f62107e7a4ae54d64b3a34c57a6d70b9b4db。仅bundle.yaml版本/evidence评测变化，新增content/policies/relationship-quality.v1.json；原12映射、关系v2/清退、source-quality、Schema/Masking等逐字节不变。用途策略canonical hash sha256:4827a94a911f23f7eed50442550416b064b3ce567e00abf018c23967ccd464c7。

静态原14关系public字段/方向/规范化评测及新5类质量评测通过：全引用、缺客户用途区分、有效行分母保留、客户删除可见、空总体不造样本。重复生成在写入前报immutable candidate target already exists。证据niushop-purpose-quality-candidate-20260914.json；无源调用/业务写入。继承对象映射不称本波重测；OCI/签名未构建更新，不具新版本发布安装资格；customer_cohort_analysis只有用途规则，尚未注册新业务Profile。

下一波SC4-5i4：原PipelineSnapshotGroupPolicyOwner抽取共用exact安装导出文件加载，保持原关系检查；新原组质量读取器在CurrentSnapshotGroupInput和原关系policy的同一当前守卫内加载exact质量策略、计算并绑定tenant/group/manifest/两个policyRef及hash，回调后重新读策略和计量防变更。只读、无数据库表、无Readiness/Fulfillment。隔离PG覆盖撤权、错版本/导出/hash、双租户、计数篡改以及旧Owner回归。

### SC4-5i4 当前组用途计量Owner验证

PipelineSnapshotGroupPolicyOwner抽取原_load_exported_document；原关系加载仍执行完整类型组与public字段检查。新增PipelineSnapshotGroupQualityOwner只在原Assessment/Input当前守卫中读取安装导出的exact质量策略，绑定原关系policy hash，计算原parents.outputRows计数；payload/hash含tenant、group、manifest、assessment、两策略ref/hash、源观察起止与全部计数/用途。同步消费后重读策略与核hash，外层继续重查权限和原输入；离开当前回调的结果是证据而非授权。

新Owner13项及旧Assessment7项隔离PG共20项12.43秒通过；补2项真实artifact hash但错误关系policy/重复JSON键拒绝4.47秒通过。测试是PG原控制/输入＋明确source/签名fixture，不冒称真实安装验收。计数/用途/源input改动，后置文件变化或release撤权拒绝；缺input不触源，错tenant/version/export/type/hash拒绝，重读始终一次源。AR2扫描1927/187/93五类错误为空。无迁移、主库、源数据或安装变化。

上一候选精确提交c4329f32：该波Receipt误写符号HEAD，随后尝试重新task-complete被已释放Lease拒绝，历史未改；本记录与新交付引用exact c4329f32澄清。当前波使用真实SHA，避免重复。

下一波SC4-5i5：核对完整首链时间/事实契约，明确业务30日窗口、当前源观察与历史cutoff的差异，以及12事实的有效行/空总体含义；形成可执行版本化方案。不能用引用覆盖取代字段/业务事实质量，不能把后来读的当前状态冒充事件时刻历史快照，也不能直接放宽现有v1。随后按原Outbox/Readiness/Fulfillment接口接消费与sealed续跑，停止继续扩充无消费者的旁路诊断。

### SC4-5i5 v3自然事件入口兼容验证

ProductEventCandidateReader和ProductEventPolicyGuard补充明确SnapshotMappingV3类型；来源仍由原SourceSelectionOwner当前编译/授权，原selection scope、shop、parent、事件证据、时间窗和同步回调检查不变。无新查询、事件时间修正、Case创建或安装。

Red5 failed/15 passed（5.26秒）证明当前v3被旧类型白名单拒绝；修复后连原callback测试31 passed（9.00秒）。覆盖v3正常、错shop、错parent与执行前/中到期。上述是明确Owner fake的接线测试，不是主系统端到端验收。AR2扫描1927/187/93五类错误为空；已有客户与数据库未变。

后继SC4-5i6：根据原事件Origin的runId查找唯一原组manifest成员，验证same cutoff而不是仅按时间拼组；定位返回只是路由，仍须原组当前Owner和原Store/投影证据验证。当前组控制为运行中守卫，未来完成态回读必须专门实现生命周期合同；不得为让分析继续而把已完成schedule假装running。正式12事实/人群计量与Outbox消费继续待做。主安装仍旧版本，不能将兼容代码等同线上恢复完成。

### SC4-5i6 原运行快照组定位验证

PipelineSnapshotGroupLocator复用原member唯一键联查claim/input，要求runtime租户事务；精确验证原binding/requestHash、manifestHash、run成员顺序和cutoff，返回原group/actor/control-run bindings。缺原input/未知run返回None，不按时间猜组、不读source、不赋予当前执行或Readiness权限。

隔离PG10项覆盖：逐成员定位同组、准备前None、未知run不替换、差1微秒拒绝、错tenant/非法输入拒绝、原唯一约束、原binding/manifest损坏拒绝。首次测试误按调用顺序比较，修正为原Owner的control resource_id排序；后一次9过1夹具失败，原FK正确禁止修改已引用requestHash，改为测试专用破坏binding body而保留原FK。最终损坏反例2项5.11秒通过，其余9项在前组合通过；未放宽产品约束。AR2扫描1928/187/93五类错误为空。主库/数据未变。

下一波SC4-5i7：给原GroupClaim/Input/Assessment/Quality增设独立completed-current只读入口，复用原单run read_completed_current和ControlledIngressJournal(completed_read=True)，要求组内全部成功/执行器已停/原Dataset Receipt与完整投影记录合格；默认running写路径不变。定位到组后仍需此当前只读守卫。暂不支持换控制代次的组续期，不把完成态历史变成新写许可。

### SC4-5i7 完成组当前只读验证

原GroupClaim/Input/Assessment/Quality新增独立read_completed_current/run_completed_current；内部逐成员复用原SourceClaim.read_completed_current和ControlledIngressJournal(completed_read=True)，每次核成功/停止/完成时间/原Dataset回执。默认reserve/run_current/GroupObjectExecutor未扩大到完成态；同一原控制当前权限仍要求。返回原input计量，非最新规范对象、正式Readiness或新写入授权。

隔离PG新完成态8项＋原Quality15项共23项24.03秒通过；再跑原GroupClaim/Input/Object28项23.89秒通过，共51项。测试用原对象/图/Dataset执行器生成实际回执，运行终止状态明确为夹具设置；不是主系统调度完成实测。验证完整组只读重放一次源、默认写路拒绝、任一成员running/failed/未停/无finished/缺Receipt/hash坏拒绝，以及消费中当前release撤权拒绝。AR2扫描1928/187/93五类错误为空；memory-status强投影CURRENT、validateGREEN，eventual Codex pending不手改。主系统仍未升级或安装。

下一波SC4-5i8：组合原AnalysisContinuationContext、origin.runId和精确cutoff定位器、完成组QualityOwner，在同一当前事务绑定analysis Receipt、原组manifest与策略。要求定位actor/controlRef和原analysis source journal完全一致，不接调用方自报run/group/时间，不更新旧需求截止。组合先补原始分析上下文与组之间的读取接线，随后该输入用于固定事实测量与原DataRequirementOutbox消费；不会把引用覆盖直接当Fulfillment。

### SC4-5i8 分析原始快照上下文验证

AnalysisSnapshotContext复用原AnalysisContinuationContext，固定原completed journal的scope/actor/run/control；运行编号和cutoff只从原上下文取，Locator回读原组，GroupQuality完成态当前守卫计量。绑定analysis context+quality payload hash，防消费方修改。case analysisType须在安装用途策略中。不接手工group/run/cutoff参数，不创建DataRequirement/Fulfillment，不调用模型。

组合10场景与原AnalysisContinuationContext5项合计15项覆盖。首次规范JSON拒绝计量用途tuple，修复为证据载荷数组而保留Owner原计量不变；重跑14 passed/1测试夹具失败29.21秒（list iterator不属于原生成器延迟合同），将夹具改成真正generator后该项5.78秒通过；未修改原全局guard。正常、原组不符、cutoff差1微秒、actor/control/purpose不符、结果改动、release撤权均验证。实际完成组用PG原对象/图/Dataset回执；分析源上下文为明确named double，另跑原上下文5项门禁；不能合称真实完整首链验收。

AR2扫描1929/187/93五类错误为空，无主数据/安装或外部动作。下一波SC4-5i9：真实只读聚合核对当前30日订单/订单行群体、删除/未知/未来时间及客户缺口分布，输出无客户标识计数；决定首个正式业务事实计划用实际经营统计还是启动计划研究，不能先假定有近期样本，更不能改legacy initial_store_analysis v1的空分母和100%阈值。其后固定事实查询、原DataRequirementOutbox消费者与Fulfillment仍需组合。

### SC4-5i9 真实经营窗口核验结果

2026-09-14 20:25:51—20:25:53北京时间，当前P02配置，同InnoDB REPEATABLE READ READ ONLY事务，1.276秒，无客户/订单标识或财务数据导出，无业务写。窗口2026-08-15 20:25:51至09-14 20:25:51（此诊断两端含），不声称历史快照/Fulfillment。

Order185：active125=历史120+近30日5，deleted60均历史；近30日5笔客户缺口0，27笔active缺客户全在历史120笔中，另5笔deleted缺客户仍历史。近期创建最早08-22 16:01:36、最晚09-09 14:54:45。这里只是未删除订单，不代表支付/成交，不能给出GMV、利润或增长因果。OrderLine235：父active历史161+近期5+父deleted历史69，自身create_time235条全未知；父订单均可定位且其创建时间可归窗，没有missing-parent/unknown/future分组。商品65=上架39+下架18+删除8；此前57是未删除口径，并非57上架。

计数与先前185/235/65以及客户32=27+5对账。脚本重复执行在任何source调用前ValueError拒绝，原证据未覆盖。固定业务计量必须按用途和窗口先确定范围：历史客户缺口不能污染近期订单群体，也不能被抹掉；订单行用真实父订单时间而非造本行时间；商品在售、未删除两口径分列。5笔样本只能支持描述和经营假设，不能作强统计结论。

下一波SC4-5j1：实现受控快照的声明式业务群体选择（维度/自身时间/父订单时间）及计数分区，保留unknown行，不把缺父/坏时间从质量分母消失；完整raw cohort保持用于关联和溯源，业务窗口不物理删数据。以5笔近期/历史客户缺口、39上架/18下架、订单行未知自身时间作为测试案例。随后字段质量/人群政策与正式QualityEvidence、原DataRequirementOutbox消费合并；legacy v1阈值不动。主库/安装未变。

### SC4-5j1 业务样本选择验证

新增纯业务群体selector：完整声明12类（通用规则也可用于较小已验证组）的snapshot/own-time/parent-time；绑定原关系hash，父时间必须使用原策略已声明positive-id关联。可选known/accepted状态明确，原始快照/历史不改；known范围外或显式删除才excluded，缺父/坏时间/未来时间/未知状态留unknown。observed=excluded+eligible，eligible=included+unknown，unknown不能当有效分数。窗口[start,end)，非历史状态重建。

先Red模块不存在，后样本/原关系质量/原正式需求质量共61项4.55秒通过（8warnings）。5近期/120历史/60删除订单、39上架/18下架/8删除商品为真实聚合规模构造的单测，非再读source；父订单时间替代未知行时间仅用于业务归窗，未写回伪造createTime；缺父与非法ref仍保留质量分母。编译hash/漏类型/重复规则/未知父/未声明关联/状态集合/窗口边界拒绝。AR2扫描1930/187/93五类错误为空，无主数据/安装或新外部调用。

下一波SC4-5j2：冻结1.18基础上生成1.19候选，新增initial_store_analysis业务群体策略：Product在售子集，Order创建时间窗，OrderLine/Shipment/Payment用已声明Order关联与其创建时间；Shop/SKU/Category/CustomerLite/Weapp/SystemConfig/ProductReview是当前观察维度（Review明确不代表近30日评价统计）。保留全raw供关联/历史；规则不改旧DataRequirement语义或替代逐事实字段质量。SC4-5j3再从原analysis上下文读取实际pending DataRequirement，绑定其window/purpose/current head/生命周期与安装导出cohort策略，使窗口不是调用方手填；随后正式测量与消费者。

### SC4-5j2 Niushop 1.19业务样本策略候选验证

新增1.19候选，仅修改bundle版本和静态eval，增加business-cohort.v1.json；12映射及原关系/用途质量策略保持字节不变。目标树sha256:dd15e696a3962610e88bf2fef3cb1f843d97d3760be8aeafe0a8e035ba49957f；cohort策略sha256:1b59787c347ca02b382fa0823956c403664e8638eac75926a1cb5c0998a83274。

静态核验公开字段、12类声明、历史订单范围、未知时间保留、缺父保留、下架分离通过；原14关联候选与5项用途质量检查通过。重复生成在目标存在检查处拒绝，未覆盖原候选。旧1.18树保持sha256:5f3c6c00002c184429ceaaeca626f62107e7a4ae54d64b3a34c57a6d70b9b4db。没有重跑对象映射eval，没有构建签名、发布、安装、source读取、主库修改或正式Fulfillment。

下一波SC4-5j3：从原分析上下文的实际Run读取当前pending DataRequirement，绑定真实窗口/用途/生命周期与安装导出的业务样本策略，禁止调用方手填运行或窗口；继续保持legacy阈值和空分母约束。主系统真实首链及八场景仍待正式计量、安装切换、续跑和连续观察。

### SC4-5j3a 原始待处理需求上下文验证

AnalysisPendingDataContext复用原AnalysisContinuationContext事务，参数仅原receipt_ref与同步consumer；原Run验证WAITING_DATA/RUNNING及pending ref，原DataRequirement精确/当前版本一致、未过期、无blocker，原Case/Compilation/TaskRun/Checkpoint、Profile/facts/purpose/cutoff逐一核对。原窗口/阈值不修改，消费前后重读并校验载荷hash；不产生Readiness/Fulfillment或执行经营步骤。

Red因模块未实现而失败。首轮7 passed/2失败，失败为测试取消操作actor与createdBy不符，修正夹具沿原created_by执行，生产规则不变。新增9项+原需求创建18项合计27 passed/37.88秒；再补无pending和已取消Run两项后新模块11 passed/15.67秒（7 warnings）。实际PG原请求/暂停/取消Store与原分析continuation运行；源与能力沿用明确fixture double，漂移场景部分为reader double。不能称真实完整首链。没有源调用、主库迁移/安装或模型执行。

AR2初次发现新Host模块未分类；复核其仅协调Host权威且使用原growth Profile目录，清册新增Host分类一行及初始hash，旧preHash与验证器不改。复验1931扫描/188分类/93迁移，五类错误为空；强一致投影CURRENT、memory-validate GREEN，Codex eventual PENDING_ASYNC仍不阻断。

下一波SC4-5j3b：组合原pending上下文、原completed snapshot上下文与当前安装导出的SnapshotBusinessCohortPolicy，实际需求窗口/purpose绑定到selector，并保留缺时间/缺父unknown。只给出受控样本输入，不冒充逐事实字段质量或合格Fulfillment；后续正式字段计量、原Outbox消费者、主环境安装切换、真实首链/八场景和持续观察仍未完成。

### SC4-5j3b 原始业务样本组合验证

AnalysisBusinessCohortContext以原pending Owner包裹原snapshot Owner，两analysisContext hash一致、需求cutoff等于组观察截止，窗口取真实需求；在原安装锁内读取SnapshotBusinessCohortPolicy导出并核version/hash/release/purpose，原完整outputs选择included/unknown/excluded，不删除raw或授予质量分数。结果绑定两个上下文hash与需求、样本策略ref/hash，消费后复验策略及输出，原Owner继续复验当前权限。

Red模块缺失，Green新增10 PG 36.09秒，原pending11+snapshot10回归21 PG 34.85秒通过（7warnings）。新增测试使用实际completed组/对象/Dataset回执，分析与pending为named doubles；原pending独立PG真实请求/暂停/取消及原snapshot10检查补充，不能合称真实完整首链。验证上下文/cutoff/purpose/策略类型和字节不符、消费中撤权/改策略/改输出/延迟被拒绝，重放source calls仍1。AR2扫描1932/188/93五类错误为空。

主库/安装/运行服务未变，未调用模型或外部业务能力。下一波SC4-5k1：设计并实现声明式逐事实字段联合计量，按业务cohort保留unknown分母，将每类必需公开字段与该用途required关系共同判定，分别输出12类事实观察/排除/有效计数，维度和近期统计明确区别；不能以type存在/行存在冒充有效事实，不将披露关系提升为强必需，不改legacy阈值。随后安装候选/Owner计量/正式QualityEvidence及Outbox消费者衔接。

### SC4-5k1 逐事实联合字段计量验证

新增pipeline_snapshot_fact_quality.py，显式绑定cohort/relationshipQuality/purpose，每对象一组非空必需字段，固定7类严格谓词。执行复用完整cohort/关系校验与原选择器；每行所有必需字段及required关系联合成立且非unknown才有效，disclose关联仅诊断；各fact独立observed/eligible/valid/excluded/duplicate计数，空分母仍零，不跨类合并population。数值不接受bool/NaN/Infinity、身份不接受非规范前导零、时间不接受无时区/非正Unix/晚于观察。原raw不改。

原关系计量仅抽取reference_row_issues共用函数，allowedUnset/缺引用/坏引用/缺父/删除父的旧计数语义保留。Red模块不存在，初轮81 passed/5.28秒；增加互补坏字段不能平均、required/disclose用途差异后84 passed/5.38秒（8warnings），覆盖新23项及原关系18/业务cohort18/正式quality25。AR2扫描1933/188/93，五类错误为空。无主库/源读取/安装/模型调用。

下一波SC4-5k2：复核12映射的实际公开字段和业务含义，为Niushop新增版本化逐事实字段策略候选（预计1.20）；CustomerLite/Payment按public_projection，不要求已脱敏PII；金额/支付状态/商品上下架区分，Shipment跟踪号脱敏占位不能冒充真实物流信息，Review维度不冒充近30日评价。具体字段不能为通过而删改，旧initial_store_analysis阈值不动，空事实仍需原正式规则处理。随后把字段策略接入当前Owner及QueryResult/QualityEvidence/原Outbox消费者，主环境迁移安装和真实首链/八场景尚待完成。

### SC4-5k2 Niushop 1.20字段候选验证

新增1.20仅版本/eval/fact-quality.v1.json，冻结1.19与12映射/原cohort/关系/用途质量策略字节不变。新树sha256:0a5d0b369f701e5aee68d5b3692fc0b6a89b1d89d195ccd4b549f7388d5a423b，字段策略sha256:79c6a340984fb2e3b2e4cd918476da5378a70ca06c2ae00b771bdaebd0ba697d。全部字段在实际public projection或公开映射，CustomerLite无PII、Shipment无跟踪号要求、未付款Payment无payTime要求。

Order.payStatus与Review.score仅非负整数字段结构检查，不解释未知业务枚举/分值含义；记录ACTIVE不代表成交/签收。数量新增严格positive-integer拒绝0或字符串；旧predicate行为不变。Red2失败/23通过4.75秒，Green新25+原关联18/业务cohort18/正式quality25=86 passed/4.63秒（8warnings）。候选静态7检查及原14关系/5用途/6cohort检查通过；重复prepare在目标存在门拒绝，未覆盖。AR2扫描1933/188/93五类错误为空。

没有构建签名、发布、安装、源读取、主库修改或正式Fulfillment；静态完整行是构造fixture，未声称真实12类字段全合格，金额对账/跨字段一致性/业务解释仍由后续事实与查询规则负责。

下一波SC4-5k3：在原business cohort当前事务内读取SnapshotFactQualityPolicy安装导出，核exact ref/hash/purpose/两前置策略hash，完整原snapshot rows执行计量，绑定真实requirement与上下文hash，消费前后重读策略并校验载荷；沿用原pending/source守卫。仅计数输入不直接签发quality pass，后续原QueryResult/QualityEvidence及Outbox消费者和主环境切换仍待完成。

### SC4-5k3 原始字段计量上下文验证

新增AnalysisFactQualityContext，原business context只抽私有组合_run以在同一守卫中提供原snapshot；公开回调仍只收业务payload。当前安装导出SnapshotFactQualityPolicy绑定原关系/用途/cohort，requiredFacts须与字段策略全类型一致，原完整outputs按实际窗口计量，输出绑定business hash/field ref/source observation/原需求及计数，消费后重载策略并核hash，原多层守卫保留。

Red模块缺失，新增8+原business10共18 PG passed/46.90秒；正例补充真实fixture联合validCount=1断言后单项7.14秒通过（7warnings）。实际completed组/对象/Dataset回执，分析/pending仍明确named double；未宣称整条真实业务首链。事实集合/策略类型字节不符、消费中撤权/改策略/改输出/延迟拒绝，重放source调用仍1。AR2扫描1934/188/93五类错误为空，无主库/安装/源或模型动作。

下一波SC4-5l1：先完成正式固定查询存证适配方案。现有QueryResult最多100 source_refs、CanonicalQueryQualityMeasurement最多200，而完整组实测892行；不得截断来源来套合同。复核已有源证据/规范对象回执/QueryResult/QualityEvidence Owner，确定可验证的完整组来源绑定以及当前规范对象一致性，明确聚合证据与事实计数的边界、预算大小、重放/撤权/原需求语义后再编码。字段结构合格不等于金额对账、支付成功/物流签收或完整业务事实；正式Fulfillment必须继续保持原门禁。主环境迁移安装/首链/八场景与持续观察仍待完成。

### SC4-5l1 正式完整来源查询存证方案复核

新增snapshot-fact-query-evidence-design.md。对照原QueryResult100来源、CanonicalQueryQualityMeasurement200来源、真实完整组892行与原Store BASE_RECORD_NOT_CURRENT逻辑，采用完整组来源Evidence聚合引用，原存储/撤销与Owner全成员回读；不截断来源，不全局放大旧合同，不伪造hydration/历史SourceSnapshot。新增显式SnapshotQueryQualityMeasurement适配保留旧两个variant，但DTO不授予authority。

任务补入原清单：l2当前completed组规范对象/投影只读证明；l3完整组来源Evidence；l4固定QueryResult；l5显式质量合同/适用性/人口政策和QualityEvidence；l6原Outbox/Fulfillment续跑组合。每波独立方案/Lease/测试/提交。保守freshness取整组read_started_at，不用测量时间冒充source更新时间；主环境升级/签名安装/当前权限/真实首链/八场景/观察另须落实。v1空事实仍失败，若业务需要“零发货”作为可验证事实则另行版本化，不改旧要求。

本波仅方案，代码入口与字段上限人工及确定性核对完成；无新增源读取/主环境动作。下一波SC4-5l2新增pipeline_snapshot_group_projection_owner.py及PG测试，复用原ec_ingress_recovery的全部saved投影证明；如需抽取read_saved_projection_evidence先保留原completion接口语义并跑回归，禁止重新写入或恢复已completed源运行。

### SC4-5l2 当前完成组投影证明验证

新增PipelineSnapshotGroupProjectionOwner复用原completed Input/Claim，逐成员原completed journal读取全部saved parent/derived，原Store核当前base/有效事件并拒绝未projected；返回绑定manifest/claim/read interval/member control与Dataset回执hash及完整事件证明，消费后再次读取并核hash。ec_ingress_recovery只抽私有共用读取；原completion继续调用原Store.read_batch_projection_completion，新增evidence分支调用原Store.read_batch_projection_evidence，empty与缺derived旧语义不改。

Red模块缺失。首轮11 passed/5失败37.66秒：测试Store连接未设置租户导致RLS使故障注入0行、policy_denied标记属于未调用的字段策略fixture；修正为显式fixture租户并assert影响行数>0，撤权反例改为原控制Owner append实际新revision，加当前source denial named fixture。未降低RLS或改生产门禁。最终新增10+原object executor7共17 PG passed/38.72秒；原恢复/empty17 passed/5.63秒（7warnings）。实际base覆盖、事件缺失/未投影、消费中base覆盖及control superseded、Dataset坏hash、payload修改/延迟/当前拒绝均验证；source calls仍1。

AR2扫描1935/188/93五类错误为空。Store自有事务与Host仍不声称跨连接原子快照；当前证明不是长期执行许可。没有主库/安装/源调用/模型或新业务写入，测试写仅隔离schema18432。

下一波SC4-5l3：当前原字段上下文与projection proof同manifest绑定后，使用原aip_evidence表落完整组来源Evidence；内容含完整manifest/全部成员精确引用与事件证明，不保存raw客户行、不截断来源。精确hash/tenant/actor/撤销/当前重新计量验证，稳定重放无重复源读取；只有当前读取接口可供下一固定QueryResult消费，Evidence持久化本身不授予质量或Fulfillment。

### SC4-5l3 完整组来源Evidence验证

新增AnalysisSnapshotSourceEvidence，原字段上下文只抽私有_run支持原snapshot组合，公开参数不变。在原field/pending/current source与current projection守卫内构造完整Evidence，绑定原requirement、4策略、manifest、全部control draft引用与完整事件证明；source rows仍在原input，不复制raw客户行。原aip_evidence/w4撤销表、hash决定id、冲突不更新、精确列回读，2MB上限拒绝不截断。run_current按保存selection重入全部当前Owners并重建body，消费后再次查撤销。

Red模块不存在。首轮8项均在测试原AIP DDL缺twa_workspace依赖处setup失败；引入原TWA_SCHEMA_SQL的org/workspace两段后8 passed/23.81秒，生产表约束未改。增加当前base覆盖、写入后策略改变回滚及容量边界后，新10 PG+1纯容量+原field8 PG共19 passed/42.87秒（7warnings）。真实Store/Evidence/撤销/隔离/事务回滚，分析/pending为明确named doubles。892 entries只是序列化不截断与超2MB拒绝测试，未声称892行真实Owner组合验收；真实大组仍须后续主环境执行。source calls仍1，无主库/安装/源或模型动作。

AR2扫描1936/188/93五类错误为空；强投影CURRENT、memory-validate GREEN，authority AOS-000573。当前读取接口故意要求原pending任务仍有效；未来Fulfillment状态写入不得塞在这个只读consumer里，否则前后状态守卫会拒绝，应由原Fulfillment Owner负责其预期转换；历史产物展示与新执行授权须区分。

下一波SC4-5l4：使用原AipAnalystQueryStore固定查询存证，单完整来源Evidence作为source_ref，不截掉逐行来源。原requirement窗口/截止/到期，固定metric定义/列与12类计数，明确字段结构/引用覆盖边界，查询结果完整hash回读、稳定幂等与撤销/过期拒绝。先补精确方案；正式质量variant/population适用性与原Outbox/Fulfillment仍后续，真实首链/八工作台与持续观察未完成。

### SC4-5l4 固定完整快照事实查询验证

AnalysisSnapshotFactQuery仅接原SourceEvidence和精确ref；当前Owner重建全部原来源与计量后，以原固定Metric/AipAnalystQueryStore保存逐fact计数、unknown和字段/关系缺口。单完整组Evidence引用不截断来源；原requirement window/cutoff/expires、原actor、scope+Evidence+version幂等；固定partial/not_applicable，不认定经营质量。原raw request/result、hash、deadline、actor、列/行/来源全部精确重算回读。

Red模块缺失；首轮5 setup errors因测试TWA org主键误写org_id（实际id），修正fixture。第二轮3 passed/2 failed暴露原AIP8事件表SELECT/INSERT权限与FOR UPDATE冲突；补方案与单独Lease，把原Store尾事件更新锁改scope+query事务advisory锁，保留原CAS/RLS/append-only，不追加UPDATE权限。随后9 passed/31.26秒；最终新查询9+原Store回归3+两连接锁1+原SourceEvidence11共24 passed/62.41秒，7既有warnings。故障注入只在隔离schema以owner修改并恢复trigger；计数重新hash及confidence（原通用hash不含confidence）篡改仍被固定结果精确重算拒绝。Query写后source漂移全事务回滚。命名空间适配仅测试SQL表定位，原analysis/pending为named doubles；不是主环境12类892行验收。

AR2扫描1937/188/93，五类错误空；memory status强投影CURRENT，validate GREEN，authority AOS-000573。测试18432隔离schema；无主环境迁移/安装、无新增源读取/模型或外部业务写。保护overall-progress-20260913.md原+42行。主环境039–048升级、签名安装、真实新Run首链和八工作台仍未完成。

下一波SC4-5l5：新增显式SnapshotQueryQualityMeasurement并保留旧两个variant；当前精确查询+完整来源重验后生成正式逐类计量，Shop唯一scope人口策略不把不同类型相加，freshness使用原read_started_at；再接原QualityEvidenceStore，空分母/逐类阈值/撤权/过期仍拒绝。l6接原Outbox/Fulfillment预期状态转换，不能放入readonly pending callback。

### SC4-5l5a 显式完整快照质量合同

新增SnapshotQueryQualityMeasurement，schema aos.data-requirement-snapshot-query-quality-measurement/v1。严格一个完整组Evidence（id/hash一致、整数revision1、无receipt_id）和精确QueryResultRevision；旧两个variant字段不变。原evaluate_quality与QualityEvidenceInput判别器直接兼容，不复制评分器，不修改threshold/原请求。DTO只保证结构，不认证来源；l5b须原Owner当前验证和查询逐项重算。

Red缺新增类型；新合同与原质量/存证51 passed/15.17秒，旧CanonicalQueryMeasurement额外8 passed/5.19秒，共59。错误来源/重复/空引用/string revision/receipt/query类型、空分母与低质量并存、源年龄不被query时间刷新、原QualityEvidenceInput往返均验证。AR2扫描1937/188/93五类错误空，memory validate GREEN。无PG/源/模型/主环境动作。

下一波SC4-5l5b：原source Evidence当前Owner内读取固定QueryResult，原requirement完整hash/策略与逐类counts构造新测量；实际Shop唯一范围人口（不跨类型相加）、read_started_at保守freshness、原QualityEvidenceStore存证与消费时当前复核。历史已存证不作为永久许可；原Fulfillment预期转换仍l6。真实主环境12类型892行、主安装升级、真实首链与八场景仍待执行。

### SC4-5l5b 当前完整快照质量存证

新增AnalysisSnapshotQualityEvidence，原SourceEvidence仅抽内部成对回调，公开接口与Evidence body/hash不变。当前原源/字段/投影守卫内重算固定query/完整requirement，仅store/initial_store_analysis适用；原Shop成员唯一、source_pk等于mapping.shop_id、最多1行，人口按未删除Shop数0/1且与cohort eligible一致，无跨fact加总。新测量绑定fieldPolicyHash/固定metric hash/固定人口规则，freshness取原read_started_at。原QualityEvidenceStore落精确证据并读后再核；query.created_at固定历史评估时间确保同query重放稳定，每次put/read另以DB时钟判当前过期。低字段质量保存失败assessment，来源/质量撤销、过期或漂移拒绝，不产生Fulfillment。

Red新增模块缺失。初始5 PG passed/68.05秒；追加实际缺失Weapp字段导致QUALITY_BELOW_THRESHOLD并可存失败证据、写后质量撤销回滚后，新7+原Source11+Query13合31 PG passed/89.17秒，7既有warnings。全部Query/Evidence/Store为18432隔离schema真实原DDL，analysis/pending与artifact为named fixtures，人口与两类saved row是真实原测试完成组；不是12类892行真实租户链路验收。source calls仍1。AR2扫描1938/188/93五类错误空；memory strong CURRENT/validate GREEN。无主库/安装/源/模型或外部业务写。

下一波SC4-5l6a先补原Outbox/Fulfillment真实连接方案：现有AnalysisAdvanceHostService._resume_authorities和BusinessInvestigationFulfillmentResumeSaga明确依赖真实SemanticHydrationReceipt、SourceReadiness、EvidenceBundle与原mapping；Query/QualityEvidence不能冒充这些凭据。核对原语义水合、数据产物与原完成回执的可复用路径，登记精确桥接缺口；保留原Run/TaskRun/Checkpoint、Outbox/Receipt幂等、取消/unknown与当前授权。readonly pending callback不得包住预期resume状态变化。未完成此桥接/主环境039–048升级/签名安装/真实首链/八场景观察，不得宣告长程完成。

### SC4-5l6a 原完成与快照续跑连接方案

新增snapshot-fulfillment-continuation-design.md，复习双侧增长产品方案4/12/13/16节与原Outbox、hydration、FulfillmentResumeSaga、AnalysisAdvance、SourceReadiness、EvidenceBuilder。6项代码指针核对通过；无生产代码变化，不声称自动续跑已完成。原水合路径强制真实OwnerWriteReceipt；当前Source/Quality Evidence factIds空，不能充当实际经营事实。原bundle freshness_at<cutoff会把read_started<read_completed的整组观察判stale，必须显式适配政策，不能伪造观察时刻。P11旧ProductReview与包Review须版本化核对。

选定保留旧水合路径、新增显式snapshot completion并继续由原dispatch/Run/TaskRun/Receipt执行，不造水合回执。已补入同一清单l6b实际业务事实产物、l6c原bundle覆盖/新鲜度适配、l6d安装映射/原SourceReadiness、l6e原状态Owner预期续跑、l6f原Outbox自然串接、l6g完整12类组合及主环境候选部署验收。逐波先精确方案/Lease/Red，代码与实际经营验收分开。

下一波l6b首先明确商品供给、订单窗口、会员关联、渠道资料等真实可读内容及隐私边界，从原saved完整来源/cohort生产事实；不把质量计数冒充经营输入。若真实某类业务为零使旧v1要求不满足，另行定义新Profile/事实版本与新任务，不改旧hash/阈值/cutoff。主环境升级/安装/真实首链/八场景/观察未完成，继续串行推进。

### SC4-5l6b1 可配置实际业务内容计算

新增pipeline_snapshot_business_facts.py：完整绑定fieldPolicy/purpose，各fact显式records或group-counts字段；复用原cohort/quality重算，不接未经定义的新计算。records完整保留范围内公开值与unknown/invalid标记，坏值null、未选字段不导出，sourceKeyHash只是稳定定位非匿名化/领域ref；group-counts仅离散字段，known/unknown分开。历史/删除仅报告排除计数与原因，1000记录/256组/2MB超限拒绝不截断。无金额求和/成交/利润推断，factIds=[]，源认证与正式Evidence另由原当前Owner。

Red模块不存在；首轮55 passed/9.92秒，追加500条长公开文本超2MB与257分组拒绝后，新14+原field25+原cohort18共57 passed/8.06秒，7既有warnings。AR2扫描1939/188/93五类错误空；memory status强CURRENT/validate GREEN。纯计算，无数据库/源/模型动作。更正l6a描述：实际1.20的p11 mapping与关系/field策略均ProductReview，和SourceReadiness目录一致，早先Review简称不是命名漂移证据，已修正文档。

下一波l6b2：在新1.21候选包声明12类业务内容字段，继承1.20全部既有mapping/策略字节。Shop/Product/SKU/Category等记录选公开字段，Order/Shipment/CustomerLite/Payment按明确状态分组，不导出订单号、交易号、会员键、系统配置值或评价正文；OrderLine可读商品/数量但不加总当成交，ProductReview仅状态/分值分组不解释量表。候选先确定性编译/eval/重复拒绝，随后l6b3原当前Source/Query/Quality Owner落业务Evidence。候选不是已安装版本；自动续跑/主环境真实首链与八场景仍待完成。

### SC4-5l6b2 Niushop 1.21业务内容候选

新增prepare_niushop_business_facts_candidate.py及1.21.0，新增business-facts.v1.json；源1.20 tree hash保持sha256:0a5d0b369f701e5aee68d5b3692fc0b6a89b1d89d195ccd4b549f7388d5a423b，新tree sha256:33b35f7fb8dd145c4cd9700b71e396505ee1cd9cd669953a860c96304e5a2844，业务策略hash sha256:c35a535fb7852904c4ab07c7be6e0dc5d5c95af0c9e78a45ac4ba45d772d62d5。12类明确records/group-counts字段，排除订单/交易/会员标识、配置值和评价正文；商品标价非成交，分数不推断量表，渠道资料非能力健康证据。原mapping与全部既有策略字节不变；只更新bundle版本与bundle-evals，新添一个业务策略文件。

静态字段7项与业务内容7项通过，实际内容/原状态分组/未知窗口/坏值null/确定性均检查，未重跑对象写验收。重复执行在复制之前拒绝；再次核源/目标hash不变。AR2扫描1939/188/93五类错误空；memory strong CURRENT/validate GREEN。无source/DB/model/install/publish；OCI/SBOM继承数据不是新版本构建凭据，需正式build/sign阶段生成。未据静态fixture宣布真实链路。

下一波l6b3：原当前SourceEvidence守卫中加载安装的SnapshotBusinessFactPolicy并绑定同field/cohort/quality策略，完整原rows生成实际业务内容，保存类型化BusinessFact Evidence及精确当前回读。只对真正有内容并满足质量的事实声明覆盖，源/质量Evidence仍factIds空；unknown/empty/撤销/跨租户/策略变化拒绝或保留明确缺口。随后原EvidenceBundle新鲜度、Readiness、snapshot resume与Outbox仍按l6c-f推进；主环境升级与真实八场景未完成。

### SC4-5l6b3 当前实际业务事实Evidence

新增AnalysisSnapshotBusinessEvidence，原SourceEvidence当前守卫内重新读取Query/Quality原权威并加载安装的SnapshotBusinessFactPolicy。原FactQualityContext抽共享私有_load_policies，公开body与回调不变。原完整rows/cohort生成实际内容，当前人口不足时无覆盖，逐fact仅实际eligible且原评估无该类失败原因才列factIds；质量与源Evidence的factIds仍为空。保留实际值、未知与质量原因，存原aip_evidence，完整selection/subject/tenant/actor/hash/时间与撤销回读；反复消费重入全部当前Owner。业务产物非水合/Fulfillment许可。

Red新增模块缺失；初始6 PG passed/29.85秒。补入Weapp缺字段保留内容但只覆盖Shop、写后quality revoke/输出内容变化回滚后，新9+原field8+quality7共24 PG passed/81.12秒，7既有warnings。证明实际fixture业务内容、幂等、三类撤销、跨租户、原策略与结果不变；source calls仍1。原Query/Evidence/Store实际隔离PG18432，分析/pending/安装artifact为named fixtures；非主环境12类真实经营验收。AR2扫描1940/188/93五类错误空；memory strong CURRENT/validate GREEN。无主库、安装、源读、模型或外部业务动作。

下一波l6c：原EvidenceBundle覆盖继续服务端计算，新增显式完整观察新鲜度适用性，不更改旧Evidence语义，也不把freshness_at改成query时间。业务Evidence当前Owner验证、原Requirement/TaskBrief/Checkpoint与真实内容绑定后走原AipProductionContractStore/BusinessInvestigationEvidenceBuilder；精确回读/撤销/过期/重放需在新入口同时核验。先补具体方案与测试目录，原水合路径保持；Readiness、snapshot resume/Outbox、主升级安装及真实首链八场景继续后续。

### SC4-5l6c1 原暂停Task冻结简报完成代码验证

基线99b4acada；新增AnalysisSnapshotBrief及实际原w2_001/Brief Store/Receipt PG验证。复用原Task，不新建任务；当前pending/runtime/业务Evidence守卫绑定spec、原窗口与事实缺口。原Store创建并冻结，重放核当前head、hash/schema/spec/actor，写后复核Task与业务撤销。原BusinessEvidence增加run_current并保留read_current接口。AR2追加新Host分类，不改原preHash和验证器。

Red为新增模块缺失；初始fixture误带receiptId:null已按合同修正。原冻结简报禁止revise，保留该规则并另用明确存储故障注入验证head漂移拒绝。最终8新Brief加9业务Evidence共17 PG passed/80.58秒，7既有warnings。覆盖幂等、冻结不可修改、头漂移、撤销、Task变化、写后回滚。PG18432隔离ar1c schema，Task表及Brief/Receipt真实，pending/runtime/安装仍named fixtures，不是主环境真实任务验收。AR2扫描1941/分类189/迁移93，五类错误空；memory strong CURRENT、validate GREEN。

下一波SC4-5l6c2：原EvidenceBundle明确完整观察的适用新鲜度，保留原freshness_at与旧默认Store规则；当前业务Owner内创建及回读原bundle与Receipt，覆盖不足、撤销、超期和重放不得绕过。随后Readiness、snapshot恢复与Outbox自然接线、主升级安装、真实首链八场景与连续观察。无新源读、模型、主库、安装或外部业务写；不push，230 L0挂起。
