# 最新真实159副本 → 160 原迁移演练

依231/原已批准当前库恢复与独立ACTIVE Task，沿刚完成的fresh159完整恢复继续，不重做旧snapshot演练。保护qyh_current159_full_restore_r2_20261012，创建新DB qyh_current160_fresh_rehearsal_20261012 TEMPLATE该最新完整恢复库，original network-none exact lab同CID/卷，不新增端口、不操作真实源。

新增rehearse.py/原生成SQL/intents/结果均本evidence目录；reuse已冻结e17d4fc4a API树，核a160文件与当前m1字节相同，原Alembic sql=True仅159:160生成完整事务SQL，再原psql ON_ERROR_STOP在新副本执行，严禁手写替代迁移或未知重试。原源码/migration/env不改，private只存生成日志/SQL0600。

验证：647原表迁移前等于fresh基线，迁移后646业务表行数/SHA不变、仅alembic_version→160；原12序列保持、三个新journal表为空且FORCE RLS/原策略/窄writer和runtime ACL有效、writer默认NOLOGIN/NOINHERIT/无super或bypass/无Run UPDATE，保护最新159副本和真实源再次全指纹相同。实际线上签名包兼容、零执行迁移窗口、正式身份/发布/安装配置/API版本/八台/自然经营首链仍另需证据，本Task不作为授权替代。
