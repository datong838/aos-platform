# AR2-7D D1 商品观察逐行联合计量

基线64c490d8，m1串行同Task/Lease。复习231-6的先过滤后去重、坏值留分母、逐fact计量与样本单位分离，以及P02上架/非删除合同和CoreObjectRecord Product必需字段。这里只测公开源行字段的完整与合法性，不把它直接映射为完整Product经营事实或Requirement策略。

新增services/aos-api/aos_api/ecommerce_product_joint_quality.py及tests/test_ecommerce_product_joint_quality.py；登记closure-manifest.md。

固定代码政策niushop.product-public-row-quality/v1，正文自算摘要，作为实际执行规则标识，不造领域Revision Owner。政策声明：只接保真quality-observation，site1；先排除严格整数is_delete=1或goods_state=0的明确范围外行（bool不当int）；其余候选全部保留，包含未知状态。候选正整数goods_id出现重复时整组计duplicate，不任取第一条；缺失/非法ID留eligible但identity不合法。observed=excluded+duplicate+eligible，distinctPopulationCount为eligible中不同正整数goods_id数，单位product；eligible中无身份行不能被人口计数掩盖，且联合有效为0。

逐eligible行检查identity、title、availability、category、price、stock、createdAt、updatedAt八组：goods_id正整数/site_id=1；标题非空字符串；状态严格int goods_state=1且is_delete=0；分类为正整数或非空非0的原字符串（只测值存在，不证明Category外键）；价格有限非负Decimal值、库存另需整数，bool非法；create_time/modify_time为严格正整数Unix秒，<=本次readFinishedAt，创建<=修改；不使用normalizer补0、当前时间或回退。每组累计有效数，jointValidCount逐行all，不取min/平均。字段规则是本次明确可执行结构政策，不宣称覆盖Product全部业务语义、Category存在性或历史窗口。

Host reader仅HostTransaction/TenantScope与Evidence/rows/三选择refs。同一RR/SERIALIZABLE快照回读配置观察Evidence和read_bound物理Shop，核对site1、tenant、三refs及rows hash；撤销/错spec/错scope/行漂移拒绝。返回不可变计数、固定规则标识及观察引用；无原行、质量分数、satisfied、Fact或履约状态。仅SELECT，零源连接，不改旧比较/Query；后续固定Metric Query方可持久化此测量，并另行核对规范版本与需求策略。

验证：真实PG Owner和Shop绑定；各字段均有相同边际有效数但联合有效数不同的成对反例；坏值分母、重复全组隔离、范围外先过滤、bool/status、零/未来/逆序时间、缺身份、0人口、顺序不改变计数；撤销、错scope/refs/spec/hash、临时表/原Owner既有回归；本地独立复核、闭包。仅18434隔离库和fixture，不push，230 L0挂起。

复核补强：三个选择ref先检查revision实际类型仅int/str，再按原model_dump(python)正文摘要与真实Shop refs对照，不能先归一化bool为int再比较。新增revision=True对revision=1的真实PG失败反例后修复。测量时刻须不早于实际readFinishedAt，时钟倒退拒绝。

实测发现StrictInt|StrictStr的model_dump(json)也会把被修改的True序列化为1，因此仅JSON摘要不够；显式原属性type检查并使用python原值摘要，不能依赖序列化纠正类型。该中间修复反例仍DIDNOTRAISE，最终必须同一反例通过。
