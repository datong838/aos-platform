# 正式恢复实施方案（待权限门与入口实现，未执行正式切换）

## 已准备且可审阅的目标
原092和当前preview159均保留；候选aos-qyh-history159-prepared-20261011，独立aos-qyh-history159-prepared-data-20261011，数据库aos_meta_head，cluster7695302940039200809。全库647表、roles/membership/databaseACL、12序列精确对账；schema仅21处相邻AND括号重组逐项AST相同，其余行一致。备份两份，第二为校验副本，role密码未恢复。隔离networknone/noports；不是正式替换权威库。

## 产品最终要求
栖月汇真实名称、org-org/dev-project一致；当前版本8电商工作台可见并可操作，关联当前安装与有效配置；历史实例/Case/未知12Run完整保留但不重放。资源可见、只读浏览器与自然经营闭环分别验收。

## 实施路线与文件
1. **先独立入口方案与代码**：建议新增scripts/a0v_qyh_restored_http.py及services/aos-api/tests/test_qyh_restored_http.py（尚未修改），复用原signature/release/identity实现，不改a0v_current_preview_http.py现有单approved/zero-binding门。固定新container/volume/cluster/schema/tenant和明示批准对象，所有workers关闭/迁移disabled；正式有限LOGIN/外部OIDC仍必须验证，禁止aos_app/绕过RLS或开发令牌作为正式身份。
2. **完整最新包兼容核验**：历史1.10.2签名存在仅证明资源保全，当前正式选择门要求growth1.13.0；不能以1.10.2冒充最新。用现有签名当前四包的原receipt、schema/image requirements、当前Source/Owner权限与独立transport核验；必要安装最新版本沿产品resolve/lock/approve/apply/verify/configure流程，保留历史来源。
3. **批准窗口**：实际正式部署及数据库连接切换、创建有限transport/新配置/当前安装均列为独立批准范围；尚未实施，也不包含开启Host/Provider/worker、商城读取或旧Run。旧名称单行申请不被解释为本完整恢复授权。
4. **当前库完整保全**：正式切换前再记录当前preview HEAD/cluster/namedvolume/安装/业务指纹；有活跃未知结果先对账，建立零执行窗口。当前preview数据不丢弃，历史092和159副本也保留。并发任何写者未解释均拒绝切换，不能只凭Lease TTL放行。
5. **配置恢复**：三历史配置都可解码，但预算过期、旧两policy引用不符；由正式Owner在产品入口生成新的有效8来源与预算/审批，旧权限不能续期覆盖。历史99次替换/old12Run只做展示/对账，新自然尝试独立幂等键且必须授权。
6. **用户页面验收**：真实登录/租户列表名字、目标安装、8路由及只读核心交互逐一浏览器验证，复核安装字段/响应身份/版本/hash，canary零效果。状态未知、入口不可用、404/403/503须真实登记并修复，不靠截图模板或禁用fence使绿。
7. **运行与首链**：正式Host/Owner/8config/current Source/审批预算齐备另获运行授权后才能打开，按231自然计划触发，未知效果不重发；再卸载重装/恢复/8场景/连续观察发布决定。

## RED与验证范围
新增独立入口先负向：旧preview仍通过原gate；任意dbname/cluster/volume/schema/tenant漂移、历史无批准身份、开发令牌、预算失效、旧签名/配置、不一致安装、旧Run重放均拒绝；正向仅完整真实目标与有限transport的无执行启动。数据库拒写/负租户/worker关闭应测实际连接与进程，不能用mock代替正式门。

## 回滚
不删任一库、卷、备份；切换失败先停新候选服务，恢复原固定preview启动配置和原连接，回读当前数据/服务端口；不回退历史库schema、不拷贝权限或重发业务操作。未知外部结果只读对账。

尚缺独立入口实际实现和RED/正向、最新包兼容/正式身份、正式窗口批准、浏览器、首链；因此本方案不构成已部署或整Goal完成。
