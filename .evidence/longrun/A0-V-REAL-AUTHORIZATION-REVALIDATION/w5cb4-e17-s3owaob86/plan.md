# b86 完整来源发行：首次初始化竞争与正式授权接续

Rules：231/231-4、栖月汇经营执行方案、b80完整evaluator、b85b86 D-wave清单；m1唯一写者，authority1329强CURRENT，基线c4ce6c87。135真库只读，所有PG tests自有一次性库；不provision正式身份，不改变旧role/Source/Host/Provider/商城源/未知外部结果。

## 先实证首次初始化与撤销
b83已有head的锁不能证明尚无issuance/head时安全。真实PG：unissued ordinary source的SERIALIZABLE初始化快照先读0个revokes，RC raw revoke提交，再同初始化事务试写test-only issuance/head，必须不能成功提交。第二顺序初始化先持锁，raw revoke的确切PID必须阻塞，待初始化释放后成功。夹具发行只为竞争算法，不冒充Owner/Policy/合法发行。

若RED证实，仅advisory锁不足以使已建立SERIALIZABLE旧快照失效；使用不授信的source初始化协调行，与exact Evidence FK绑定，任何raw revoke与首次初始化均经过同一行。函数INSERT ON CONFLICT后FOR SHARE/UPDATE，RC事件写epoch，旧快照须40001；同事务rollback/ON CONFLICT跳过不得推进。此行只是竞争协调，不是许可证、数据真源或另一个Owner/Policy。

## 本子任务精确文件范围
services/aos-api/alembic/versions/a0v_139_license_initialization_fence.py：新增协调表，down138，无旧业务回写/自动授信；runtime只读；reuse安全NOLOGIN fence owner仅SELECT/INSERT及UPDATE(epoch)协调表；新固定scope/path definer锁函数runtime仅EXECUTE；替换原revoke trigger函数逻辑使所有合法源事件先同协调锁，再对已发行源执行原head锁/epoch。immutable父源与旧hash不变，downgrade拒关闭安全门。
services/aos-api/aos_api/aip_license_source_authority.py：新增caller-owned初始化锁；已发行读锁与revoke helper均以协调行→已发行head固定顺序。真135/旧未新增协调schema generic兼容；已存在协调表但函数缺失/缺权不能fallback。取DB真实source hash，保持原API错误/幂等行为。
services/aos-api/tests/aip/test_aip_license_source_initialization_pg.py：实际RC/SERIAL两顺序、同键重放/ON CONFLICT、0 effect rollback、exact source/scope、runtime不能写、definer安全owner/函数ACL、无License或issuance自动生成。
services/aos-api/tests/aip/test_aip_license_source_authority_pg.py：b84随机严格角色仅加新锁EXECUTE必要权，不扩大table写/issuance权。
.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob86：RED/最终日志/自审/Delivery。

## 累计与完整发行门
专项+b83–85/evaluator/原W2A/B Store/API；签名全schema；精确编译/diff、test库/本轮新role清理。没有页面改动，不用浏览器页面200代替业务验收。完成此并发子任务后必须继续原signed Policy bytes、明确来源许可的原Action Proposal/Approval、Owner当前会员/markings、独立issuer准入及issuance/head/Receipt完整事务正向；不得把锁算法、空服务或测试角色当b86整体发行完成。所有缺权只局部fail-closed，整体Goal active。
