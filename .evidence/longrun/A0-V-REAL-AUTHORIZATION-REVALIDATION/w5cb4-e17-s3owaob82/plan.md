# b82 正式来源和评估证明存储

基线01dcd8e8、authority1329；复习b80整体设计和b81连接。m1单写优先于Skill分支同步，当前135真库不迁移。此波仅建立正式命令所需存储，不把管理员fixture视为可信发行或八维验证。

具体新增：services/aos-api/alembic/versions/a0v_136_binding_source_authority.py；services/aos-api/tests/aip/test_aip_binding_source_authority_schema_pg.py；本目录证据。收尾只追加01/06/714与D-wave，不改受管authority。

新增issuance append-only、exact source head、evaluation proof append-only。issuance引用真实EvidenceBundle修订+hash、installation UUID及Registry Receipt，保留发行policy/Owner证据引用及有效期；不自动backfill，不以created_by/nonempty summary/JSON声明升权。为四列exact FK，旧Evidence仅加冗余unique索引（原三列PK已唯一，无数据更新）。head引用同tenant/same source issuance；epoch非负。proof独立绑定Binding version、installation etag、Receipt、旧依赖hash与新facts hash。结构要求八维存在，不宣称数据库验证事实语义/canonical hash/当前安装资格，这些由下一正式命令检查。

三新表FORCE RLS，runtime仅SELECT，显式撤销TI-2默认写权及PUBLIC权限；不新增/扩权任何正式login。发行/proof复用现有append-only guard；head只留maintenance owner维护能力，下一波精确SECURITY DEFINER/角色门再授命令EXECUTE，不裸授表写。installation与receipt FK是历史引用完整性，不能替代当前Owner与审批授权。

先新表缺失真实PG RED；最小迁移后验证ACL、tenant可见性、错source hash/错tenant/FK、immutable UPDATE/DELETE/TRUNCATE、普通Evidence不会生成issuance/head、schema唯一136头及相邻b81/b45/普通撤销。测试仅一次性aos_test_*_ti4_test库，自动drop；既有角色仅SET LOCAL ROLE用于ACL测试，不改变其权限。无UI变更不做浏览器。downgrade拒绝删除不可变历史或静默宽权。

风险：旧表新增unique需真实迁移时独立备份/恢复/零执行窗口；schema检查只结构不是业务验证；当前独立evaluator尚无业务权限。下一b83实现可信来源初始化与原Owner/policy/安装事实验证，不凭测试role伪造正式运行批准。Goal active，自然首链pending。

相邻实测补计划：signed全schema测试14.51s真正RED，reader已返回136，但test两处hardcode135。最小追加修改services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py：expected schema head从当前Alembic定义唯一head取值，独立对比实际reader及preview返回；不修改当前135库的恢复探针或生产reader。另登记compat Task/Lease，重跑原签名全链。没有增加生产运行授权。
