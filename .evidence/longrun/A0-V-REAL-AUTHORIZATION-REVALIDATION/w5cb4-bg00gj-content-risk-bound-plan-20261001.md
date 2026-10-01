# BG00GJ 内容Owner风险额度价格接线方案

基线AOS-001050/m1 daf01691/a0v128。复习231-5 §5/6/7、443及ContentBudgetCommandOwner、ModelRuntimeResolver、require_cost_risk、预算reserve/submit。当前真库只读，Host/worker/Provider保持关闭。

## 缺口与最小实现

GE合法风险价保留未知数字价格，ContentBudgetCommandOwner._minimum_bound_fen却在正式预算reserve前无条件拒绝development_cost_authorization，首链无法消费已批准风险额度。保留此数字计价函数；仅在_approved_bound添加需要当前事务/精确来源的风险额度分支。

- _build_command只在风险价分支从当前resolution读取selected_model/provider，重核model hash/provider/price_ref并传入同事务HostTransaction、scope、Budget/Price/Provider exact及provider_model_id。其他路径不新增Model读取。
- require_cost_risk在所有当前批准/Receipt/fence/额度检查成功后返回已验证持久price；原非cost预算仍返回None，原reserve/submit忽略返回值，原安全语义不变。Owner必须取得非None且与加载price完全一致的对象，防止把非cost预算的旧兼容return当授权。
- Owner保持正整数token限制/正预算金额，核resolved provider_model_id等于批准中值；Provider exact由共享门核验。费用批准不替代业务Action批准，_approved_action与Host revalidate原顺序保留。
- preflight只锁/更新已有cost fence，不创建hold，不计消费；真正reserve仍重验并占额，后续提交仍再验。claim及execute预检事务与真正capability commit分开；不能把预检结果当后续执行授权，也不新增重试。

## 文件与验证

1. services/aos-api/aos_api/ecommerce_content_budget_command_owner.py：上述接线；保留_minimum_bound_fen和数字价格_approved_bound行为。
2. services/aos-api/aos_api/aip_budget_cost_runtime.py：成功返回已核验price，缺消费Receipt继续None。
3. tests/aip/test_content_budget_risk_bound_pg.py：GE真签名/低权限消费/派生配置+真实PG调用Owner金额门；无上下文拒绝、合法金额正向、金额/Provider/model/price对象/预算来源/token漂移、撤销与旧快照拒绝，未创建reservation。
4. tests/extension_runtime/test_ecommerce_content_budget_command_owner.py：现有_build_command组合测试覆盖参数传递与风险分支；明确替身仅验证接线，不能冒正式Model/Action/Host权威。
5. plan/verification、444/D-waves、Task/Delivery/CAS及AOS/Prime回读。

RED→最小实现→专项+相邻预算、数字计价、Action绑定、撤销/并发累计；复审检查不复制授权规则、不填零价格、不越过缺合法Model Quota/Eval/ImpactPreview的实例禁入。纯后端无browser。无迁移/当前重启/源读取/外部调用/旧Run重放。下一波继续合法Action当前ImpactPreview及完整held联合证明；正式恢复独立安全波。只精确add，不push。
