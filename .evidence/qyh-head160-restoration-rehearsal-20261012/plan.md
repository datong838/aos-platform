# 栖月汇恢复主线当前头与160迁移独立演练

Rules231/已批准完整恢复与当前库迁移安全门，1944原代码guard已交付。候选1最新库头/160非破坏演练，候选2正式登录/独立发布原来源接入；后者既有配置路径尚待资料，不伪造身份。先候选1。

本波文件仅本evidence目录inspect_rehearse.py、current.json、intent.json、result.json、review.md、verification.json及private/source（0700/0600）；维护资源维护/qyh-head160-owned-rehearsal对应新DB qyh_head160_rehearsal_20261012，位于已授权tmpfs clone381ac0/image7e7/cluster7695416748450308141/18431。当前恢复容器qyh-restored-pg-20261011/同named volume aos-qyh-history159-prepared-data-20261011只读核identity/schema/name/count，只有SELECT无迁移/重启。原API18080只GEThealth/OIDC/me/principal及modules，仅保存status、tokenKind、tenant及模块数量/外部JWKS是否存在，不保存subject/phone/email/token/JWKS正文。已知.env和API LaunchAgent只读变量存在性，无值。

私有冻结精确git HEAD services/aos-api，排除.env和所有user改动/untracked，不改原ParentSource候选。离线先原Alembic revision map验证冻结源码唯一head160和所有模块来源（若失败报告，不创建/迁移当前库）。独立新DB以clone原aos_meta_head@159为Template完整复制，先intent O_EXCL再CREATE，模板本身不变；clone动作与真实当前库备份/零执行是不同门。原Code159已验证baseline，先全部旧普通表server端SHA256聚合/计数（仅哈希，无业务payload输出），原authoritative schema/row全保留。仅在新DB用冻结源码原Alembic159→160。迁移后逐旧表检查行内容/数量完全一致，alembic_version预期159→160，新增三表为空；writer独立角色无login/继承/超级user、Run更新权false，scopepolicy新增只读。SourceTemplate库再次hash对账，演练新库保留for验；未知结果只读核对不重发CREATE/迁移。

不把演练视为当前正式库已迁移/第二备份完整恢复/zeroexecution门，也不因此重启API/PG或开启Host/worker/Provider，原旧12Run不回放。全Goal仍须当前身份、安装配置、8页面及自然首链。任一脚本错误保留阶段日志和结果，先诊断再续，不刷新计数假提交。交付当前版本差异与非破坏演练，Dwave/Delivery/CAS/7强投影同步。
