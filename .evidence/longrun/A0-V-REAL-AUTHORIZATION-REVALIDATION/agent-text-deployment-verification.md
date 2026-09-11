# a0v_012实际恢复环境部署证据

2026-09-11，代码基线d9707de0。显式colima-aos-extension/aos-a0v-recovery-pg/aos_meta_head。m1独占，不push，230 L0挂起。

- 一次性克隆正式Alembic upgrade a0v_012成功：原518表逐表行数不变，新增aip_agent_text_output空表，ENABLE/FORCE RLS true；随后本次临时库删除。长期测试克隆f1dc保持011。
- 实际变更前独立pg_dump custom备份：4394769 bytes；SHA256 07381f7dca313a27d1275b409fbce9252d7133ba54af389d83a464a1e116ac9f。路径：/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/state/agent-text-012-20260911/before-ef2d7dd3cf7d4d328bcf1f8f1a38ce2a/backups/aos_meta_head-pre-canonical-first-install.dump。目录0700、文件0600，未入Git。沿既有helper使用no-owner/no-privileges；归档读取成功不等于完成全量restore验收。
- 实际正式迁移011→012成功；原518表行数全部不变，public共519表，正文表0行，RLS双true。未启正文retention、未写业务fixture、未调用Provider、未重启API。
- 后置检查：pg_restore --list退出0，API18181/openapi.json返回200，本波a0v_text_deploy_check_%临时库残留0。
- 原始数据磁盘、已有恢复备份及其他DB未清理。逐表行数并非逐行hash对账；迁移仅新增表/约束，不宣称真实经营闭环。
- 详细sanitized状态：.aos-recovery-20260910/state/agent-text-012-20260911/{rehearsal,backup,before-counts,result,postcheck}.json；本地执行器.aos-recovery-20260910/deploy-agent-text-012.py。
- 下一波：核对现有D03实际Task/Run调用路径，接固定prompt、显式retention和草稿接收/恢复；审批来源重验仍未补，真实source/安装/Binding仍待就绪。API服务仍旧代码，切换时需准确记录基线。
