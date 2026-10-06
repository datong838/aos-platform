# 撤回epoch设计冻结入口

依据：真实Source/allocation旧SER writer-first两RED；恢复副本pg_trigger核验withdrawal_event的RI_FKey_check_ins为AFTER INSERT NOT DEFERRABLE INITIALLY IMMEDIATE，当前无其它用户trigger。

原则：不得照搬Evidence BEFORE touch。正常Store持proposal UPDATE后插withdrawal；直接INSERT的FK检查持proposal KEY SHARE。若epoch先于FK，可能构成正常Store proposal→epoch与直接INSERT epoch→proposal逆序死锁。首版采用严格AFTER INSERT、名称zz_capacity_withdrawal_epoch_bump_a0v151，要求全部INSERT FK立即且排在新trigger之前；migration及运行审计必须核此不变量，拒绝未审延迟FK/重排。不凭SHARE/KEY SHARE推断阻塞：实际epoch UPDATE与reader SHARE形成wait/40001。

独立NOLOGIN/NOINHERIT/无高权/member owner只拥有独立epoch表/3函数，无原proposal/withdrawal表额外ACL。epoch(org,project,proposal_id) bigint>=0；仅org-org/dev-project，表FORCE RLS，owner exact scope；初始backfill所有正向proposal，epoch=count原withdrawal事件；迁移原行不改。proposal AFTER INSERT仅初始化epoch（须匹配scope），withdrawal AFTER INSERT UPSERT并epoch+1；非目标租户不增加记录/不扰原流程。reader lock函数仅FOR SHARE、禁止懒创建，缺行/epoch>0拒绝；旧SER读被修改行产生40001，原native入口必须拒绝、调用者回滚，不自动重试。

reader位置：Source guard完整super.check_proposal返回（含原metadata/Owner/Provider/Evidence及checker）后，解析原Source payload allocation_approval_ref对应proposal，Source+allocation两个id去重排序取得epoch锁。原allocation内部只作原存在性检查，不在其前半段获取新锁。之后查撤回并拒绝；未来publication新域锁只能排其后。SQL函数SECURITY DEFINER/search_path=pg_catalog、PUBLIC全部撤权；仅runtime和privateissuer reader EXECUTE。proposal/withdrawal写触发函数不授runtime/issuer直接EXECUTE。

接口兼容：新函数必须纳入private issuer入口精确function/role/schema审计，不能简单放宽所有EXECUTE；原Evidence owner审计不变。Source guard仅正向原流程加门，无真实Source签发授权。

待实施范围：新增a0v_151_capacity_withdrawal_epoch.py（down150）、新withdrawal fence helper及PG测试；原Source action集成属于formalBoundary Task，private connector及原RED测试属于Source Task，分别先同Owner对账续租，不交叉夺Lease。publication未来迁移顺延152（原151 publication文件尚未创建）；需在原publication方案/Task范围显式对账后才编码该未来迁移。当前150恢复证据保留，不宣称其覆盖新151；151加入后最新代码/源迁移恢复安全门必须重新登记。

退出：双writer-first RED转GREEN；reader-first Source/allocation实际pg_blocking_pids等待、提交后writer完成；原normal withdraw/普通Action兼容、backfill旧撤回/缺行/伪owner/function/ACL/延迟FK/触发禁用/错scope反例；Source+formalBoundary+原Action累计回归。原当前库不迁移/不重启，完整业务Goal保持active。

## 2026-10-06 历史回填验收补充
只读实测既存150恢复副本正向proposal=0、withdrawal=0。该副本151升级只能证明其实际历史兼容，不能证明非空撤回回填。后续在本Task文件 services/aos-api/tests/aip/test_capacity_withdrawal_epoch_pg.py 增加独立非空150历史迁移用例：保留原proposal/withdrawal快照，执行真实151 upgrade，核epoch准确计数、未撤回为0、原行无变化、撤回锁拒绝；坏原数据或前置门失败须证明DDL/版本事务回滚。副本151升级另在恢复Task登记安全门后执行，不复用旧150完成结论。
