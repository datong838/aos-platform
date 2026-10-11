# 历史092全库隔离恢复

Rules：AGENTS、aos-engineering-delivery、231-3/4/9、D-wave历史实例恢复兼容清单。

候选一名称正式修改仍待授权；候选二历史全库隔离恢复，为正式恢复兼容必需且不依赖真库写入，本轮选择二。

源固定aos-a0v-recovery-pg/aos_meta_head@092、原cluster7683855731447750695、原image/命名卷。查bootstrap aos_app OID10与源无其他会话；源只读fingerprint、pg_dump一致备份及globals无密码。私有备份目录0700/文件0600，git排除；第二份为校验副本，不冒称独立snapshot。

目标aos-qyh-history-restore-20261011，原镜像、network none、无ports/sourcevolume、独立tmpfs1G。保留原bootstrap aos_app OID10，globals仅跳过一次匹配CREATE ROLE；所有ALTER和grantor保持。全量pg_restore失败保留日志，不改为部分恢复。逐表原排序MD5/count指纹比较并再次回读源。

只新增本证据目录及已登记D-wave。无API/worker接入、无旧Run执行、无当前库写入。此波只证明全数据备份恢复，不证明角色密码/schema全部语义/ACL/迁移兼容或业务可运行；后续67步迁移与禁入独立验收。
