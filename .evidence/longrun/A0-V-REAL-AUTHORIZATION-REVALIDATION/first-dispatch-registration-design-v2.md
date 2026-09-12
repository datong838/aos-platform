# 电商首装九路由登记设计 v2

2026-09-13；基线97e09d5f。按用户持续开发及真实栖月汇验证授权开展产品实现，m1串行，不push，230 L0及外部发布不在范围。

## 当前事实与原设计遗漏

05:18权威库当前九路由、业务ScheduleBinding、Occurrence均0。CanonicalRouter严格拒绝未登记路由；Cutover.prepare_activation要求已存在完整九项legacy/fence=false路由。PG测试由fixture预置这九行，因此不能证明真实首次安装入口完整。

05:20只读ACL复查：独立非superuser/bypassrls的runtime登录采用aos_runtime后，对dispatch绑定实际有SELECT/INSERT/UPDATE/DELETE；maintainer仅SELECT。实际ACL与ar2_001所定义runtime只读不同。恢复库宽权限来源仍需单独追溯，不据此直接INSERT，也不声称角色收敛完成。证据dispatch-entry-current-observation-v1.json及dispatch-entry-role-acl-v1.json。

## 产品行为

安装完成配置后，用户在正式安装控制入口登记已验证包声明的九项经营路由；一次原子登记，全部默认不可执行。登记仅创建固定元数据与不可变Receipt，不运行Case/Run，不读取商城或调用模型。重复同一请求返回原Receipt；同键异载荷、已有组、部分组、跨租户、安装/配置漂移均拒绝。

登记后用户可以审阅exact登记Receipt与固定九项操作，再由既有切换审批体系激活。首次未激活登记也必须能安全卸载/替换；不能要求不存在的切换Receipt才能清理未启用登记。

## 实现清单与依赖

1. 新增登记契约与预览服务：固定操作集合来自ECOMMERCE_GROWTH_OPERATIONS，不接受调用方自选handler/SQL。输入installation ref、generation、binding revision、execution epoch、config ref、idempotency key，当前persisted角色与markings核验；预览不是授权。
2. 独立迁移新增append-only登记Receipt，记录tenant、安装/配置/lock摘要、组ID、九路由snapshot、actor、requestHash和时间；RLS、不可变触发器、唯一tenant/idempotency。精确登记函数只创建完整默认fenced组及Receipt，专用maintainer执行，无任意表写权限。新访问能力需完成针对性权限评审与隔离PG负例后才正式部署，不借用当前runtime宽权限、超级用户或fixture执行真实登记。
3. Cutover.prepare_activation增加“真实首次登记”来源：只接受登记Receipt证明的完整legacy/fence=true组；既有legacy/fence=false路径保持原样。禁止泛化为任意fenced组可切换。prepare/commit/rollback/replay均保留exact snapshot及审批核验；回滚恢复原fenced状态。
4. 正式安装控制API接入登记Owner，依赖身份/安装/配置现状，无直接数据库后台脚本替代。固定九路由的角色与markings检查复用安装控制权限服务。
5. 未激活登记在禁用/卸载/替换时以专用不可变撤销Receipt释放或转移占位，禁止无痕删除、禁止在新generation继承旧执行权。已激活路径仍由现有cutover/lifecycle所有者处理。
6. 完成当前主库权限差异清单及代码迁移定义对照，确保部署不依赖宽权限。回退不删除历史Receipt或降级RLS。

## 最低测试门

拟修改文件（逐项施工前再核对所有权与现状）：
- services/aos-api/aos_api/ecommerce_growth_registration_contracts.py：严格请求/只读预览/Receipt契约；不接数据库或授权。
- services/aos-api/aos_api/ecommerce_growth_registration.py：正式登记Owner，复用当前安装与配置读取、角色/markings校验。
- services/aos-api/alembic/versions/a0v_026_dispatch_first_registration.py：专用登记及撤销Receipt、受限入口；仅在权限评审完成后部署。
- services/aos-api/aos_api/ecommerce_growth_cutover.py：仅支持带真实首次登记Receipt的fenced起点，保留旧路径。
- services/aos-api/aos_api/routers/bundle_runtime_installations.py：正式安装控制登记/预览入口。
- services/aos-api/tests/extension_runtime/test_ecommerce_growth_registration_contracts.py、test_ecommerce_growth_first_registration_pg.py：新增契约和实际隔离数据库验收；旧cutover/lifecycle/OCI测试继续保留。

迁移文件名为设计预留，实施时仍需核对最新迁移head，不能因预留号覆盖既有文件。独立的权限评审结果与真实部署结果必须分开记录。

### 首个代码切片：请求与预览

Request复用CurrentInstallationRef、ConfigurationRef；generation、groupId为严格规范UUID字符串；bindingRevision、executionEpoch为正的严格bigint；幂等键复用安装控制校验。extra forbid，不接受operationIds、handlerKind、actor、SQL、credentials等任意注入字段。固定schemaVersion区分未来版本。

preview只输出请求hash、exact安装/配置引用及九项legacy/fence=true/revision1的拟登记snapshot，明确executable=false、authorityValidated=false；组内installation/generation/epoch保持null，真正目标仅在请求中记录，不能绕过切换。输出是分离字典，修改预览不会改变请求或后续hash。验证未知字段、UUID/数值拒绝、同请求hash稳定及任一exact字段变化hash变化；不声称本切片完成登记持久化。

- 无既有路由→一次完整九路由fenced登记，CanonicalRouter仍拒绝；同请求重放无重复。
- 双写者同scope、不同组ID竞争只允许一个完整组；任意已有部分组拒绝且不补齐。
- 跨租户、错店铺配置/安装版本/lock/generation/epoch、无当前角色/markings、未知操作及普通runtime/Web身份均拒绝登记。
- 中途失败整事务回滚；Receipt不可更新删除；禁止普通身份直接改dispatch。
- 首次fenced登记的exact审批切换、配置漂移、过期撤销审批、commit崩溃重放、rollback恢复fenced；旧legacy路径回归。
- 未激活登记可禁用卸载重装，已激活须先fence/drain/detach，不能绕过旧generation任务排空。

## 经营首链接续

登记与激活完成后接源事件消费者：SourceSelection/current配置校验→按事件存在性扫描而非MAX revision→冻结deadline→record_event_batch→CanonicalRouter→initial_store_analysis。下架/删除事件要撤销旧候选，候选状态函数不能过滤事件流。需要新版本平台包纳入候选状态规则；当前签名1.5不改动。真实成功门是Case/Run和后续业务产物，而不是九行登记或测试通过。
