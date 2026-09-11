# 恢复基线升级及备份恢复验证

日期2026-09-11；代码基线5654f2d7；m1单写者，不push，230 L0挂起。

## 新鲜证据

显式colima-aos-extension/aos-a0v-recovery-pg读取aos_meta_head：a0v_001，512张public表。pg_dump自定义格式4523083 bytes，sha256 b693df98a218a10cb11a34bee0e4e7b0208ade0fc446369bb35311b030d34ede。原库全过程仍a0v_001，未迁移、未终止连接、未重载API。

第一次恢复stdin未启用docker exec -i，报input file too short；确认空库后修正传输参数。第二次完整恢复在data_source_configuration_revision CHECK失败：规范化函数递归调用未固定search_path。不是备份损坏，也不允许跳过数据。

新增a0v_011只给public.canonical_asset_registry_jsonb(jsonb)固定pg_catalog,public,pg_temp路径；不变更函数正文及哈希规则。隔离克隆实测修复前空路径UndefinedFunction，修复后嵌套对象/数组输出与原值一致；调用者schema同名函数不影响public函数内部递归。forward-only防止恢复已知路径缺陷。

历史备份兼容恢复：新建aos_upgrade_check_726a74487d2c，分别恢复pre-data，在此克隆应用a0v_011函数设置，再恢复data/post-data，三段退出码均0；然后正式Alembic a0v_001至a0v_011全部成功。这个修复步骤仅针对历史备份，不能将旧备份原样恢复称为通过。

将升级克隆重新pg_dump，原样pg_restore到全新aos_upgrade_check_f1dc452abade：退出码0；实际版本a0v_011；518张public表逐表行数完全一致。原Journal与恢复claim表ENABLE/FORCE RLS均true。逐表行数不等于逐行内容哈希对账，也不等于真实首链/完整从零安装验收。

受限本地详细结果：/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/upgrade-checks/aos_upgrade_check_10f11e023a30/repaired-upgrade.json。dump目录0700，dump0600，未入Git。三个诊断库保留，不能广泛清理其他数据库。

## 结论与下一波

已证明恢复基线升级及修复后新备份恢复路径；现有恢复库仍未升级，真实源仍缺连接，API仍旧基线。下一波核查经营参谋现有业务计划入口与自然触发断点，复习当前运行授权后准备实际服务切换。经营参谋形成有来源业务计划，不用虚构计划填同步计划空态。总目标仍是首链、八工作台真实场景、连续观察和发布评估。
