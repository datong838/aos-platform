# W5CB4 E17-s1｜Skill 发布来源与签名 Eval 持久读证验证

## 方案、RED、实现

- 先读 231/231-3/231-9、56 技能发布产品方案、64 W-F2/F3、552 与原 Skill Registry、Eval Runner/Writer/Reader、ReleaseGate 代码，再写 `w5cb4-e17-skill-publication-source-plan-20261003.md`。当前普通 Eval Runner 与 ReleaseGate 对 Skill 均硬拒；签名 writer 已有双 Receipt/Report/sidecar 原语，但缺正式成功 Run/issuer/identity/Owner。故本波只补发布门前的**只读、同快照、持久来源装配**，不删禁入。
- 新增隔离 PG 测试首次运行 exit 2，`ImportError: read_verified_skill_eval_report_from_persistence`。最小实现在原 `aip_eval_report_proof_reader.py`：核 `aos_runtime`、精确租户和稳定事务；从原持久 Suite 取独立 input hash，精确读取同 Run/Report 每 case sidecar、双 Receipt 和 identity 证书，交给原逐 case reader 验当前签名、撤销、Run、Report 与结果。没有写库、签发或发布调用。

## 可复核验证

| 检查 | 命令/结果 |
|---|---|
| 新增隔离 PG 六情形 | `AOS_DATABASE_URL=<当前权威实例仅作为创建临时库的连接> .venv/bin/python -m pytest -q tests/aip/test_aip_eval_report_persisted_assembly_pg.py`；6 passed，exit 0。测试会创建并删除 `aos_test_*_ti4_test`；正向签名是 test-only，失败项含错 Suite hash、缺 sidecar、撤销、跨租户和 read committed。 |
| 相邻发布回归 | 同环境运行新增测试 + `test_aip_release_publication_service.py` + `test_aip_skill_publication_service.py`；21 passed、1 xfailed，exit 0。该 xfail 为原有项，不作为通过。 |
| 静态与现场 | `python3 -m py_compile` 两个目标文件、`git diff --check --` 目标源码均 exit 0。`curl` 8080 `/v1/health` 与 8434 `/aip/skill-publish` 均 200；18181 无 LISTEN。`docker inspect aos-a0v-recovery-pg` 显示权威卷 `aos-a0v-recovery-pg-data`；只读 `SELECT version_num FROM alembic_version` 得 `a0v_135`。 |

## 方案一致性、风险与下一波

- 代码仅实现计划第 1/2 项的受限只读装配；未改变旧 reader、Eval Runner、ReleaseGate、Skill 发布、绑定或当前实例。计划第 3/4 项继续 pending。新函数的正常返回只证明报告持久签名来源在隔离测试事务中可验证，**不等于** ReleaseGate 通过、正式发布、active SkillBinding、Plan frozen 或自然首链。
- 独立 writer role/ACL、正式 issuer/Target/Judge 身份及 EvalRun 创建 Owner 当前仍缺；当前真库只读，未申请角色、凭据或改数据。下一波先把发布 gate 的 Skill 分支改为同一 serializable 事务消费此装配结果，并做当前撤销/错证/多 case/重放负例；保留原普通 Runner Skill 禁入。随后才接合法 EvalRun/签发/绑定来源。浏览器无 UI 修改，本波不复用页面 200 作为业务通过。
- 与 552 一致：六个 `SKILL_BINDING_NOT_ACTIVE` 仍是 Plan freeze 的正向障碍，不能以 test-only 签名 fixture 或手工行替代当前正式来源。
