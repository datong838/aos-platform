# W5CB4 BG-00e｜D01 当前 canonical Eval 来源只读结论

- `m1@9a14c769`、当前 `aos_current_preview_20260927@a0v_111`、命名卷 `aos-a0v-recovery-pg-data`；22:18 完整重启记录另见 `w5cb4-daily-latest-stack-20260928-2218.md`。
- 容器内 `psql -U aos_app -d aos_current_preview_20260927` 以 `BEGIN READ ONLY` 精确查询 `org-org/dev-project`：`ecommerce.skill.D01@1` 为 `evaluated`，hash `ef9d469841ba7776bb1b109ea9fffc6cdca99ac024500133348428e4c1bf9058`；`aip_eval_dataset_revision`、`aip_eval_suite_revision`、`aip_eval_run`、`aip_eval_report_revision`、`aip_release_gate_decision`、`aip_publication_event`、`aip_skill_binding` 各 0；`ROLLBACK`，退出 0。未查商城业务行或写当前库。
- `AipEvalPackRegistry.register_suite_revision` 仅从已注册同租户 Dataset exact ref 起步；`AipEvalRunner.run` 需要实际 Artifact resolver、target executor 和 judge executor，正式 Skill 产品接口尚未接入。旧 `/v1/evals/*` 只服务 Logic compatibility。历史 BI-W10 D01@2 hard-coded 选择函数自称 historical，不能套到当前 D01@1。
- 当前不存在合法的 D01 Eval 数据集/脱敏 Receipt/Case/Judge/执行器/报告，故不开放当前实例正向放行，不以合成或页面状态替代。下一波先完成独立的 SkillBinding Owner API 产品接线，但它必须只接受已正式 published 且同租户的精确 Skill；当前 D01 仍会被拒绝。之后回到 D01 真来源生产者。
