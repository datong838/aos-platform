# 正式恢复实施方案（整体恢复已获授权；当前安装与API八页面仍待实际验收）

## 当前实施澄清（2026-10-11，AOS-001847）

用户已明确授权今天恢复栖月汇租户、电商域全系统及数据卷，并纠正偏离域/租户的配置；之前“完整正式恢复待批准”的阶段记录已被本次授权取代，不再重复索要整体恢复授权。单写m1、保留旧库/卷/备份、未知结果不重发、旧12Run不回放等边界继续有效；独立发布账号、正式Owner/身份与运行审批预算不是被自动授予的权限。

- 同一保留647表卷aos-qyh-history159-prepared-data-20261011/cluster7695302940039200809/aos_meta_head@a0v_159已加载于qyh-restored-pg-20261011/loopback18446，有限NOINHERIT LOGIN/SCRAM；原092与preview159仍保留，当前API仍指向preview，尚未切换。
- 当前选定core1.4.3/platform1.23.2/Growth1.13.0/operations1.2.2；统一公共目录179文件精确，8模块签名解析、3实际缓存镜像与恢复库3schema receipts隔离诊断通过；3会话各2048heartbeat且清理独立确认。上述诊断不等于真实发布、安装或Host权限。
- Core1.4.3/Growth1.13.0已在恢复库由原Registry create/validate，仍validated；同制作身份publish曾被职责分离门拒绝，未重发。保留两基础包仍published。647表除5个预期Registry表外其余642表精确保持。
- 生产别名接线提交57e45d5ff；公共根134039493；混合诊断44fa0f202；当前安装只读入口60c7fc99d。入口复用真实发布/lock/签名校验，不使用诊断PUBLISHED投影冒充实库状态。
- 当前入口34专项/相邻通过、9PG依赖测试明确跳过；另有先前控制接线权限测试桩失败已独立登记。实库三个叶均在org-org/dev-project：407/899仍Core1.4.2/Growth1.10.2，ef5仍Core1.4.0/Growth1.10.0，均不能当本次当前四包安装通过。
- 全恢复Task仍ACTIVE。下一项：使用真实独立发布身份完成原Registry发布，按产品resolve/lock/approve/apply/verify/configure更新安装和有效八配置；核正式有限身份/OIDC、沿受支持入口PG→最新m1 API→Web、栖月汇八页面与只读交互/canary；Host/worker/Provider及自然首链另守当前正式权限门。

实际证据：aos-platform/.evidence/qyh-full-system-restoration-20261011/plan.md、registry-two-validated-readonly-reconciliation.json、mixed-candidate-qualification-terminal.json、current-installation-entry-verification.md及current-installation-exact-lock-coordinates.json。下文保留早期阶段记录，仅用于历史审计，不作为当前等待整体授权或停止施工依据。

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
