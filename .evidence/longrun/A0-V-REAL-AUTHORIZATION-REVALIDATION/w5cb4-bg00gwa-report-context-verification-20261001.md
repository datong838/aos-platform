# BG00GW-a Report context 保真验证

Task W5CB4-BG00GWA-REPORT-CONTEXT-20261001，进入基线 AOS-001064 / 825c7de4。

## 实现与范围

原 atomic writer 在同一事务中保存原模型已有的四 JSON refs + evidence_cutoff_at，SQL NULL 保留为 NULL。新增 aip_eval_report_context.require_same_eval_context 供原 writer preflight 与 persisted proof reader 共用：阶段四绑定完整且有合同；四 JSON refs 按原 JSON 值严格比较（bool 不等于 int）；cutoff 必须 aware 且同一时刻。
原签名、Issuer/Identity、Dataset/Suite、Run 状态、角色、RLS、serializable 与 case proof 检查保持；无 schema/ACL/签名用途变更。没有创建新的阶段执行入口，也不把上下文一致当成正文已被评测。

## RED → 修复 → 回归

API cwd `/Users/ddt/work/projects/ai_agent/aos-platform/services/aos-api`。

1. RED 命令 `.venv/bin/python -m pytest tests/aip/test_aip_eval_report_context.py -k roundtrip -q --tb=short`，exit1，1 failed/9 deselected/4.85s。原 writer 已提交，原 AipEvalRunner.get_report 回读不等于提交 Report，失败在 `assert reread == report`。日志 /tmp/aos-gwa-red.log，SHA256 d8c2a5a8f12d5e99dcb44d9344c600e51698e9494b84d316704dbbd17da325ad。
2. 首次修复验证 exit1，9 passed/1 failed/4.61s。reader 漂移测试逐个置 NULL 被原 ck_eval_run_media_subject_pair_w7_004 先拒绝；没有关闭约束，改为全字段保留而引用/时刻变更来触达 reader。日志 /tmp/aos-gwa-green.log，SHA256 aa548edcf66ef5f293989b3a25f43e751b67598bf44d97bec73d85c98ce5e31c。
3. 最终专项 `.venv/bin/python -m pytest tests/aip/test_aip_eval_report_context.py -q --tb=short`，exit0，11 passed/4.63s。日志 /tmp/aos-gwa-green2.log，SHA256 2b6b73cd519f759501ab40fcaf93d268f138f89c0bdae84a1530ac39a2e6eb2f。
4. 累计命令如下，exit0，48 passed/6.13s，零 skipped，不与专项相加。日志 /tmp/aos-gwa-regression.log，SHA256 eedde8edf06bfd4da1fdb26c4d9973f1bd6f776f6b781c4f2c356ac25188eef0。

```sh
.venv/bin/python -m pytest tests/aip/test_aip_eval_report_context.py tests/aip/test_aip_eval_execution_authority.py tests/aip/test_aip_eval_runner.py tests/extension_runtime/test_analyst_stage_eval_report_proof.py -q --tb=short
```

5. 五个本波 Python 文件 py_compile 与 `git diff --check` exit0。

## 隔离与证据强度

- 标准 conftest 创建并迁移一次性 `aos_test_*_ti4_test`；新增 fixture 在写前硬检查数据库名前后缀，不消费当前权威库或旧专用恢复库。
- 真实独立 NOINHERIT login、原 identity file 0600、原连接身份校验、原签名预检、真实 PostgreSQL INSERT、原 Report reader/proof reader；未 monkeypatch writer/preflight/reader，也未打开 AOS_EXTENSION_PG_TEST。
- Issuer、签名执行 Receipt、Run、Suite/Dataset 与上下文是具名隔离测试来源，不是 D03 实际模型执行。测试没有 Provider 调用，不构成真实阶段或首链验收。
- 五个错误 context 各自重新计算 Report hash 后仍被 preflight 拒绝，每次三张输出表均为 0；最终匹配报告完整往返；随后逐项修改 Run fixture，原 persisted reader 均拒绝，修改 rollback。
- null/contract-only/stage 三种既有形态通过纯一致性检查；实际独立登录 PG 往返覆盖 stage 形态，未将纯检查说成三种形态全部实际 PG 验收。
- 临时 login 在 fixture finally 撤销并删除，identity 文件删除；fixture 行和数据库级测试授权随标准一次性库清理。全程串行测试，未修改现有全局 writer 角色属性。

## 复审与剩余风险

修复与方案一致：原数据保真及上下文一致性，不增准入权。测试不依赖手工放宽原 DB 约束。生产 writer 对历史缺失字段的错误记录仍会读失败，不能自动回填未知事实；如遇此历史记录应只读核对，不重发评测。
本切片 GREEN 仅为 Report metadata roundtrip；签名 inputHash 是否覆盖阶段正文/完整上下文、正式阶段 Eval producer、accepted stage decision 到旧 Handoff 仍未接通。下一步继续 GW-a 输入签名/合同完整接线设计与 GW-b 原 Handoff adapter 审查。GT 模型用途权限与正式 OIDC/API 身份待答不变。当前真实实例未迁移、未重启、未启 Host/worker/Provider，未浏览器验收。本切片按9步收口；整个 GW 首链接线仍未完成。
