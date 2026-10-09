# v3身份原件同调用者只读桥

Rules：231八步、AOS工程交付、先方案后最小代码、m1唯一writer/精确scope。当前AOS-001677；已登记候选一同调用者v3身份只读桥，候选二SourceTTL/审批撤回竞争（原生产者持锁与新原件依赖）；选择一，不扩大Root/正式权限。

产品/技术依据：231主计划首链垂直闭合及231-1四层权威边界；当前原描述只读门已在实际occupation SCRAM事务观察原件。旧runtime_executor_fact_statements仅读v1 certificate_identity_binding；新v3私有reader要求issuer Owner，不能跨连接/SET ROLE后伪称原physical caller。新增单独module/test/证据，不改旧v1/v2或扩全表权限。

SQL只读函数显式隔离安装，SECURITY DEFINER issuer Owner、固定pg_catalog、PUBLIC撤权、runtime仅EXECUTE。必须exact occupation session_user/runtime role/SERIAL/UTC/origin/双tenant；精确plan/hash/description/risk/当前xidpid，原v3binding中的origin相等；完整case-purpose集合，不缺/重复/混旧v1。root→certificate→identity稳定排序锁，读取原bytes及真实current epoch/global撤回，返回不含执行授权。禁止新prepare/INSERT/UPDATE/COMMIT/table grants/role repair。SQL不能代替Python严格v3原文canonical/hash/header/Ed25519/有效期/leg/candidate等签名合同。

Python用同一个实际physicalconn：原Source和Owner/原description验证，再读取v3metadata并解析签名原件；最终Source/Owner/原description及metadata currentness/真实时间复核。保持原锁序，不能以第二连接结果替代同caller。并发/失效不得缓存成current。方案复审特别核查锁顺序；发现持锁跨域冲突先补方案，不猜测实现。

RED先证明新窄桥缺失且旧v1/v3私有入口不等价。专项纯验不连DB；native用现有ownedlab freshDB，私有metadata独立COMMIT仅准备态，原风险原件在physical事务，结束实际COMMIT拒绝/四表0。精确前后hash/ACL/SQL/DB身份只读对账；未知结果不重发，保留全部失败。独立root只是实验bootstrap，不证明trusted provenance；正式HostworkerProvider仍off。无UI更改浏览器不适用；最终复审/verification/精确提交/CAS/上下文，不凭计划或单测交Delivery。

尚未实现/未验：窄SQL原件集、Python同caller全复核、native全矩阵、root谱系、WALACK/transport及经营链。本Task ACTIVE，无Delivery。

实现初步复审：SQL集合计数用独立整数变量，避免record混合INTO；wrapper核对manifest原bytes/canonical/typed全文，final metadata之后再用实际数据库clock逐证书复验有效期，避免前次验签跨后续等待失效。先进行ownedlab事务内DDL编译/管理员负门，显式回滚且确认函数未持久化；此步骤不替代实际occupation正向/并发矩阵。

实际数据库语义RED：physical SERIAL已经读取Source/风险后，后续独立issuer事务COMMIT的v3描述绑定元数据不在其原快照中。原DB双只读连接零表写实验：后续xid已COMMITTED而pg_visible_in_snapshot=false、原snapshot不变。当前独立COMMIT→samecaller读取方案不能声称可接线；SQL编译/静态约束通过不解决此依赖环。禁止降隔离、第二连接替换、角色修补。暂停此设计内错误接线动作（不暂停Goal），必须先复审签名/原件生成时序或独立新协议；现有只读artifact保留为未交付草案。另有已登记SourceTTL/审批撤回竞争可独立推进。
