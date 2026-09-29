# W5CB4 BG-00i D01 正式 Eval 来源只读审计

日期 2026-09-29；前置 BG-00h `m1@36d1bb03`。本波只读核验，不新增代码、不注册 Dataset、不读取商城源。

## 方案/Owner 复习

- 231 总控与 231-1/5/9、栖月汇全店经营方案要求真实有来源事实、精确评审与授权；AIP-4 E1A/B/E2 要求不可变 Dataset manifest、Case Artifact、Judge exact ref、Runner Report 与 ReleaseGate。
- `aip_eval_contracts.py` 的 manifest 有 source id/revision/hash、字段白名单、脱敏 Receipt、PII 状态和 case count；`aip_eval_pack_registry.py` 登记 Dataset 时只比较 source hash 字段，Suite 只复核 Dataset ref；`aip_eval_runner.py` 接收外部 Artifact resolver/target executor/judge executor 回调。当前没有 D01 的正式生产者接线。
- `ecommerce_content_pre_review_pack.py` 的 `_sample()` 是明确的隔离评测正文与固定样例引用，目标是内容 LogicGraph；不得用来发布 D01 Skill。

## 当前权威库只读结果

容器 `aos-a0v-recovery-pg` 绑定原权威卷；`aos_current_preview_20260927` 的 `alembic_version=a0v_111`。全部查询在 `BEGIN READ ONLY`/`ROLLBACK` 内，scope `org-org/dev-project`：

| 元数据表/范围 | 行数 |
| --- | ---: |
| `aip_artifact` | 0 |
| `aip_artifact` 中 eval/redaction/case type | 0 |
| `business_investigation_redaction_receipt` | 0 |
| `aip_research_artifact_receipt` | 0 |
| `aip_eval_dataset_revision` | 0 |
| `aip_eval_suite_revision` | 0 |
| `aip_eval_run` / `aip_eval_report_revision` | 0 / 0 |
| `aip_release_gate_decision` / `aip_publication_event` | 0 / 0 |

`information_schema.tables` 当前无 `%judge%` 表；JudgeRevisionRef 目前只是 Suite 的精确引用字段，并非独立可读取的发布权威。BG-00h 新 API 的两个当前租户列表也均 `200 []`。本审计只确认这些正式表缺失，不把其他平台存储推断为空，也不推断商城没有业务数据。

## 判定与下一独立工作

当前 D01 不能建立可核验的正式 Dataset/Case/Judge/Runner→Report→Gate/Event；不能使用旧 Logic Eval、测试样例或手工写当前库绕过。BG-00j 应先实现同租户 Artifact snapshot 与脱敏 Receipt 的只读来源前检（精确 hash、类型、版本、白名单与缺失码），在隔离 PG 证明跨租户/错 hash/缺失/失效全部拒绝；它本身不登记 Dataset、不声称评测或业务首链。Judge/执行器正式权威需要随后独立接线。
