# 栖月汇历史实例恢复兼容清单

## 当前实施澄清（2026-10-11，AOS-001847）

用户已明确授权今天恢复栖月汇租户、电商域全系统及数据卷，并纠正偏离域/租户的配置；之前“完整正式恢复待批准”的阶段记录已被本次授权取代，不再重复索要整体恢复授权。单写m1、保留旧库/卷/备份、未知结果不重发、旧12Run不回放等边界继续有效；独立发布账号、正式Owner/身份与运行审批预算不是被自动授予的权限。

- 同一保留647表卷aos-qyh-history159-prepared-data-20261011/cluster7695302940039200809/aos_meta_head@a0v_159已加载于qyh-restored-pg-20261011/loopback18446，有限NOINHERIT LOGIN/SCRAM；原092与preview159仍保留，当前API仍指向preview，尚未切换。
- 当前选定core1.4.3/platform1.23.2/Growth1.13.0/operations1.2.2；统一公共目录179文件精确，8模块签名解析、3实际缓存镜像与恢复库3schema receipts隔离诊断通过；3会话各2048heartbeat且清理独立确认。上述诊断不等于真实发布、安装或Host权限。
- Core1.4.3/Growth1.13.0已在恢复库由原Registry create/validate，仍validated；同制作身份publish曾被职责分离门拒绝，未重发。保留两基础包仍published。647表除5个预期Registry表外其余642表精确保持。
- 生产别名接线提交57e45d5ff；公共根134039493；混合诊断44fa0f202；当前安装只读入口60c7fc99d。入口复用真实发布/lock/签名校验，不使用诊断PUBLISHED投影冒充实库状态。
- 当前入口34专项/相邻通过、9PG依赖测试明确跳过；另有先前控制接线权限测试桩失败已独立登记。实库三个叶均在org-org/dev-project：407/899仍Core1.4.2/Growth1.10.2，ef5仍Core1.4.0/Growth1.10.0，均不能当本次当前四包安装通过。
- 全恢复Task仍ACTIVE。下一项：使用真实独立发布身份完成原Registry发布，按产品resolve/lock/approve/apply/verify/configure更新安装和有效八配置；核正式有限身份/OIDC、沿受支持入口PG→最新m1 API→Web、栖月汇八页面与只读交互/canary；Host/worker/Provider及自然首链另守当前正式权限门。

实际证据：aos-platform/.evidence/qyh-full-system-restoration-20261011/plan.md、registry-two-validated-readonly-reconciliation.json、mixed-candidate-qualification-terminal.json、current-installation-entry-verification.md及current-installation-exact-lock-coordinates.json。下文保留早期阶段记录，仅用于历史审计，不作为当前等待整体授权或停止施工依据。

依据231-3/4/9；org-org/dev-project，原cluster7683855731447750695。历史092库不是当前159预览库，不直接切换或继承旧执行权。

- [x] 历史安装/配置定位及当前解码哈希核验；证据qyh-historical-installation-reconciliation/qyh-historical-configuration-refs-20261011。
- [x] 已定位运行策略ref4/head13不一致及预算策略过期，禁止直接沿用。
- [x] 旧092全库一致备份、第二可校验副本、独立全库恢复与578表数据指纹；源前后不变，无网络/ports/原卷挂载。第二份为校验副本。
- [x] 恢复库roles/成员/grantor/数据库ACL精确一致，11序列参数及last_value/is_called一致；schema仅15处相邻AND括号重组逐项AST核验，其他行一致；原578表保持。角色密码不在验收范围。
- [x] 092→159原67步逐步实际提交，577旧表历史行保持，16原迁移元数据逐字段及151回填182条epoch双向集合精确一致；旧安装/配置一致，binding禁用且fence=true。证据qyh-historical-migration-20261011/final-independent-readback.json，源库仍092且原578指纹不变。
- [ ] 最终159目录/配置兼容、签名身份与正式恢复方案；隔离迁移不等于正式恢复或浏览器八工作台通过。
- [ ] 整理正式恢复范围/批准资料：保留当前库、旧12Run未知效果仅对账，不复制active/失效配置。
- [ ] 当前真实实例正式恢复/新配置/签名与身份HostOwner门、八工作台浏览器、自然首链验收。

本轮Task qyh-historical-full-restore-20261011：只备份与隔离全库恢复；不改真库，不启动API/Host/worker/Provider，不读商城源。不删除任何旧库/卷/备份。

159原目录解析有效runtime候选3组/12bundles，8模块资源存在；三binding均disabled/fenced；原97aeb配置解码通过但policyhead不符。97aeb非有效叶，唯一正式恢复实例/签名文件/页面仍待核，不可直接恢复旧active。证据qyh-restored-catalog-compatibility-20261011/result.json及formal-recovery-scope.md。

替换图111→3叶链长1/100/10：97aeb后继ef5；Canonical407独立；899承接旧12Run。三配置均当前解码通过但预算过期，旧两叶policyhead不符。保留四较新签名包当前验签/Registry artifact/contentHash精确一致，8模块实际加载。历史旧四版本未在所选root找到。Task qyh-installation-lineage-signature-20261011；下一登记持久化恢复预备/固定启动门与正式恢复实施方案，不能绕过权限或重放旧Run。

持久化副本aos-qyh-history159-prepared-20261011/独立命名卷与cluster7695302940039200809完成647表全库恢复、roles/membership/databaseACL、12序列一致；21处CHECK相邻AND重组AST相同。无端口/无服务，三目标binding保持禁用，原库不变。正式方案见qyh-durable-restoration-preparation-20261011/formal-implementation-plan.md；下一登记独立恢复入口（新增scripts/a0v_qyh_restored_http.py与专项tests）先RED、保留原preview gate及正式身份权限，latestgrowth1.13.0不能被历史1.10.2替代。正式切换仍待批准。

当前1.13原构建/资格/签名tree与发布策略、3 exact本地镜像、恢复159的3 schema receipts/所需relations重新核验通过；Registry已有core1.4.0 hash冲突（1.4.0/1/2全published），Growth1.13未登记，平台/operations一致。不能覆盖旧坐标。下一登记core1.4.3新unsigned候选及独立恢复构建profile/RED/原profile回归，细案qyh-current-release-recovery-preflight-20261011/core-successor-plan.md。未签新包、publish、安装或切库。
