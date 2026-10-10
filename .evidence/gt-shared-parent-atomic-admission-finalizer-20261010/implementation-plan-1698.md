# 完整共享父风险原子准入与finalizer实施计划

Rules：231、原joint实施§3/§11.3、最小更改、单m1写者、未知效果不重发。Task10仅准备能力已官方交付，不再修改其scope。完整长程目标不缩小。

## 原始要求与新版本边界
一次真实准入COMMIT必须包含当前signed Source/身份/独立审批、精确两个父预算、全case四腿描述和cert、唯一Target Intent与Judge pending dependency、首个物理义务和不可变准入Receipt。外部Target/后继Judge在已提交准入后执行；Target实际结果是Judge后继依赖，不能在准入里伪造。所有风险保留并与原预算原算法共用；unknown/Source更新/到期不能自动返额或重新派发。

原准备artifact七个deferred检查使用无条件拒绝函数。完整新版本不能将该旧函数改为常真、关闭trigger、SET ALL或删原FK，不能把Task10的prepared_only row提升成正式Receipt。采用明确隔离的新版本入口和完整生命周期，原准备路径保持拒绝。新路径须复用原预算/Source/物理算法及核验核心，而非复制简化alg或另造fake来源；需要提取common kernel时，须在对应现有Task精确scope先登记计划，逐字验证旧生成SQL/已安装函数body hash、权限和所有相邻行为不变。新版本计算必须纳入旧未决风险；无完整切换、历史映射和独立签名来源则禁入，不能以表空推断正式权限。

## 精确文件与接线
本Task产品scope：services/aos-api/aos_api/aip_shared_parent_atomic_admission.py；services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py；证据位于本目录。两个产品文件仍未创建，不把登记当实现。
支持接线必须逐文件回读既有Task归属：aip_physical_capacity_occupation_authority.py（当前回读属Task1）、aip_physical_capacity_occupation.py（原Task1）、预算/模型Owner及contracts（对应原Task），不能创建重叠Lease或在本Task冒写。需要新迁移时先核代码head和迁移分配，再单独登记该精确文件；不重写已发布版本，真库仍只读。

## 必须完成的流程
1. 当前原Source签名/安装事实、两原真实批准request和parent hold同native caller/xid/pid；费用fence→物理account update→三桶固定序，禁止callbacks/普通Task替代Eval。
2. 明确新版本kernel与保存模型及old unresolved兼容切换；全请求父上界与物理累计不重复持有，第一Target Intent唯一，Judge等待真实Target结果，非执行签名/描述不能当当前准入。
3. 全manifest/cert/identity锁先取得，保存准入可信Receipt及所有实际effect。完整event fixedpoint/RI/C verifier/索引比较/函数和native部署来源全部精确冻结，不能以部分catalog代替真实queue。
4. 所有实际等锁与当前性读取先于最终DB clock决策；结束入口仅一次真实COMMIT，early SET/多结束命令拒绝。决策点不是WAL/ACK；若需实际COMMIT期限，则定义提交后可信确认和超时非执行/风险保留协议，不能修改需求或事后假rollback。
5. 独立连接在首次synthetic dispatch前核唯一已提交Intent/风险/Receipt；原worker unknown journal不重发语义必须保留。后继native Target结果consumer核独立COMMITTED origin/当前Root/head/实际transportUsage，Judge须组合v3签名与exact输入门，最终发布/currentResolver同证明。
6. 原生全准入positive、每节点故障rollback、hash/replay/不同caller/canary、读者先/写者先撤回与期限竞争、early COMMIT/SET、后续触发等锁跨期、未知提交只读对账；原预算/physical/正常Content邻接、适用浏览器、方案代码复审、Delivery/精确提交/上下文。

## 当前选项及实测第一步
候选一完整新版本准入/finalizer：用户已批准设计/隔离实现，依赖上述核内复用与完整结束门；本轮选择原生目录RED，确认旧七个拒绝门仍完整、候选新入口缺失，明确版本差距后推进kernel文件级接线。候选二正式native部署/Root信任：已登记，但需要正式签名来源/独立发布资料，不能用实验bootstrap替代。二者均不触达当前真库、真实Host/Provider或旧12Run。

## AOS-001715 维护后完整新版本接线调查
原维护执行已知终态、当前159真库恢复只读。本Task同owner租约已对账续期，无重叠，无Delivery。候选一为完整新版本准入/finalizer，已批准隔离实现但必须复用原可信facts并计入全部旧未决风险；候选二正式native部署/Root来源，依赖独立正式签名不执行。选择一：新增本目录admission-kernel-binding-1715.py/json，静态生成精确原SQL并抽取CREATE表/INSERT/UPDATE/SELECT锁、实际deferred guards、容量计数与继承需求；核原14生成器对1699beforeimage逐字相同，原七拒绝门保持。禁止用这份静态清单证明native queue/完整准入GREEN。产品两文件仍未创建；本步不访问数据库、不安装函数、不触达Provider。下一实施以显式新版本tables、旧风险兼容mapping及完整结束通道为同一个交付包，不能通过替换prepare或关闭七guard获得正向。
