# W5CB4 BG-00bw｜正式网络元数据 a0v117 文件级方案

## 上位依据与当前边界

复习 231、231-5、41 网络策略实施清单、BG00bv 审计、Producer `_OBJECT`/`_ACTION` 合同与 a0v115/a0v116 迁移。当前 m1 `9b5d34a3`、权威库 `aos_current_preview_20260927@a0v_116`；Host/worker/Provider 关闭。当前正式 ObjectType/ActionType 两行缺失，正租户第二真实 checker 缺失。本波只解决静态元数据来源和数据库保留 ID，不生成身份、提案、批准或 active 策略。

## 变更文件与判据

1. 新增 `services/aos-api/alembic/versions/a0v_117_network_formal_metadata.py`。迁移先要求两个固定 ID 均不存在，使用审定的 Producer 合同逐字段插入 `NetworkPolicyRevision` ObjectType 和 `aip_activate_network_policy` ActionType；创建 `meta_object_type` 固定 ID 的 owner-only INSERT/UPDATE/DELETE 触发器。拒绝已有行漂移，不做 upsert/覆盖；downgrade fail closed。a0v115 的 ActionType 保留门、a0v116 的 active 禁入门均保留。
2. 新增 `services/aos-api/tests/aip/test_aip_network_formal_metadata_pg.py`，在显式 test-only 全库克隆上 RED→GREEN：迁移前缺行、迁移后字段精确、runtime 写固定对象被拒、普通对象仍可写并回滚、ActionType 固定 ID 仍受保护、active DB 门仍有效。
3. 仅在独立的当前切换波更新 `scripts/a0v_current_preview_http.py` 预期头并重启服务；本代码波不碰当前库。迁移目标采用明确的 `a0v_116→a0v_117`，不得对其他库名误执行。

## 验证与恢复

先在全库备份恢复的 test-only 克隆升级，比较五张安装控制表 count/row digest、触发器和角色写边界，运行专项与相邻回归。若进入当前库切换，必须重新停 API/Web、核零执行窗口、新一致备份 SHA/TOC、第二全库克隆恢复及全链检查后，才允许迁移当前库并重启 PG/API/Web。任一失败保持现有 a0v116 服务和 active 禁入，不修补生产数据。退出结论只能称元数据注册，不称正式审批或业务首链通过。
