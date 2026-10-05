# b90在真实当前142之后的完整方案复核

Task w5cb4-e17-b90-current142-plan-revalidation-20261005，Authority1330，current真实142/代码20bb251d与5d1f67e5，实际维护a51039e4已交付；不再以135迁移未完成阻断此代码波。原current库恢复只读边界，Host/worker/Provider关闭，CapabilityBinding0/runtimeBinding0。后续a143只允许登记后的隔离实现，不直接迁移当前。

复核原service.evaluate：原有角色分流已拒capability_lifecycle issuer作正式evaluator，但普通store仍先self.get/外部readiness评估，再另写事务；它不是b90同事务八事实正式命令。当前网页skill发布37修订显示缺正式Gate/Logic/Route/Policy，binding入口待接线，数据库没有Source实际发行/正式evaluator LOGIN；不能靠重启升级业务准备。

完整原八facts/Source/Owner/安装/预算/原Receipt-CAS-proof必须共同实现。当前计划锁序发现需在开码前闭合的具体潜在循环：原Source issuer先Proposal→Approval→两Owner→Installation→init→Registry/draft；evaluator若先Owner/Installation后再锁原Approval，与issuer等待Owner可成环。先无效力发现exact Source IDs，再按稳定ID取得原Proposal/Approval共享锁，再两Owner/Installation/Source init/head；所有无锁发现字段在受保护事务内重新核验，不用无锁发现授许可。不得简单给reader追加锁而逆转Owner顺序。ModelRuntime writer/Health epoch/Capacity锁同样逐个原路径核对，完整无反向序后登记代码Task。

Health必须协调所有可达原DML而不建立第二真源：旧healthy行FOR SHARE不能阻止new unavailable append提交，已actualPG反证。拟a143中性epoch只用于原观测并发协调，reader锁住当前epoch后核验原最新observation；writer需沿原DML触发更新epoch，post-snapshot原40001按真实机制验证，不以同快照再读自证。不能对旧健康事实backfill或承诺最新healthy缓存。

下一本Task补完整逐表/列/RLS/SELECT-for-lock ACL清单、Source原核验纯函数提取边界、六类Model head与Health/Capacity实际writer顺序、原绑定命令与同调用方事务hash/expiry/原三记录延迟COMMIT约束。然后登记完整a143/formal evaluator/service consumer及实际PG tests范围；不能先交付较小DTO/reader并称b90完成。原Health RED Task与未实现完整消费者事实继续有效，Goal active。

## 10:42 原写者锁序与已有未提交草稿复核

本次只读复核基线cef84e51/AOS-001330；memory-status七强CURRENT、memory-validate GREEN。本节为已登记方案Task的设计补证，不是a143代码授权或GREEN。当前真库142未执行DDL/DML，未启用Host/worker/Provider。

### 已核实原写者

| 原入口 | 实际锁/事务顺序 | 完整消费者约束 |
|---|---|---|
| `AipModelRuntimeStore._publish` | 本kind head FOR UPDATE → `_validate_dependencies`精确revision普通SELECT → head CAS及immutable revision/Receipt → 内部commit | selected heads按固定类型/id先取得共享锁，再复用原读者；当前依赖验证没有跨head锁，不能凭getter宣称已锁当前head。不得调用publish或record_health进入评估事务 |
| `AipModelRuntimeStore.record_health` | 原Receipt回放 → Provider exact revision普通SELECT → observation INSERT → 原Receipt → 内部commit | fence必须覆盖原表DML，不能只改该Store；仍保留原幂等/回滚与唯一健康真源 |
| `AipModelCapacityReservationGate.reserve` | pool head FOR UPDATE → 该run reservation FOR UPDATE → 原pool到期reservation UPDATE → 占用SUM/COUNT → reservation及event → commit | evaluator锁同pool head并只读原有效占用；避免先锁reservation再请求pool head。原有效状态reserved/consumed且expires_at>NOW，量子为token_unit_per_reservation |
| `AipModelCapacityReservationGate._terminal` | 单reservation FOR UPDATE → reserved变consumed或released → event → commit；不请求pool head | consumed不增加原有效计数/token，released只减少占用；对可用额度判断为保守变化。proof只能说明checked_at可用，不能把占用数字称为提交时精确持有或替代真正reserve。raw特权写者仍不是正式执行权 |
| `AipModelGovernancePolicyStore.require_exact_active` | quota在非read-only事务共享锁head；budget部分分支通过get_budget_head普通读取 | evaluator须显式锁选中quota/budget head后复用核验；禁止把Budget getter当前快照当受保护当前性。治理publish own head FOR UPDATE，需继续核对正式approved activation入口及其审批/Owner先后 |

原Source issuer顺序已查明Proposal → Approval → 两Owner → Installation → init → Registry版本/证据 → draft。消费者无效力发现exact IDs后，稳定顺序锁Proposal/Approval，再Owner/Installation及Source；锁后重新核验发现字段。主plan中旧“binding→Owner先行”段须统一修订，不能让补充段与主合同矛盾。

### 未提交Health草稿尚不能验收

10:42工作树存在`services/aos-api/aos_api/aip_binding_formal_evaluator.py`及`services/aos-api/alembic/versions/a0v_143_provider_health_epoch_fence.py`两个未提交文件，均不在现有Health RED Task的代码scope内。仅阅读并保留，不覆盖、不提交、不称完整evaluator或已登记实现。现有第三个Health测试只验证post-snapshot一种竞争，不能替代正式身份/全DML/同caller事务证据。

1. 草稿fence按完整provider_ref的md5协调，而helper latest SQL按assetId取全部revision/hash。草稿返回请求ref而非核验观测实际ref，可能让其它revision/hash的观测影响结果且该写者不共享所锁fence。合同冻结为tenant/provider-id同一协调域，最新观测必须与请求exact type/id/revision/hash一致；不同exact引用也进入该provider协调域，不能健康回退。
2. UPDATE更换tenant/provider_ref时草稿仅COALESCE选NEW，旧key无epoch更新；多key须稳定排序并同时协调旧/新资源。跨租户改写应由原RLS/不可变保护拒绝，不靠缺GUC偶然拒绝。TRUNCATE在注释声称覆盖而实际无trigger，必须确定原权限明确拒绝及适用维护入口，或提供可验证协调；不能留可绕过路径。
3. SECURITY DEFINER Owner拥有fence表却未FORCE RLS，owner绕过表policy；touch/bump未显式核验caller tenant，且未撤销trigger函数PUBLIC EXECUTE。必须与原Source fence身份模式逐项对照并实测拒绝，不以有policy文字称租户隔离成立。
4. 草稿shared reader调用INSERT ON CONFLICT初始化，产生写权限依赖并可能与并发writer冲突；既有历史observations没有epoch。初始化只建立中性协调，不填造健康状态；区分共享已有行和受控缺行初始化，实际串行/共享reader及首次writer竞争必须测试。正常已有行不能因不必要INSERT而误称纯共享锁。
5. md5仅作为键而未检测provider_ref碰撞，且updated_at超出原“tenant/resource/epoch only”合同。优先直接使用明确provider-id资源键，不需依赖完整JSON摘要或新增健康真源字段。
6. helper用datetime.now及把naive时间补UTC，未严格native connection/tenant/SERIAL身份校验；epoch fetchone按tuple而其后按dict访问，与既有dict_row连接不一致。必须复用固定连接身份与真实DB clock，不默补时间或接收任意conn；缺expiry和非healthy状态不能成为正向事实。完整命令最终消费Health facts/hash并在原三写实际COMMIT校验最小expiry。
7. 现有“complete_evaluator_has_current_health_transaction_consumer”只检查callable。模块存在会令该旧缺模块RED消失，却仍没有完整八依赖命令。须追加实际完整命令行为RED，缺Source/Capacity/当前Owner及安装必须零proof/零binding版本变化/零Receipt，而不是以模块可导入称GREEN。

下一有限审查清单：签名安装原_reader内部锁；治理approved activation/预算消费及Eval当前decision写者锁图；原binding/proof/Receipt逐列ACL与延迟约束；Source纯验证原函数边界。完成并统一主plan后，按精确新增/修改文件另登记完整代码Task。上述草稿风险均为源码审查结论，尚未跑实际PG验证，不标为实测失败或业务拒绝。
