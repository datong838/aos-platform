# Subject-review 信封验证

用户已授权两项方案的实现/隔离验证；本波仅完整信封与canonical待签名输入，不是签名权威、Owner接线或运行许可。
- 两次仓库根误用.venv路径退出127；已改用services/aos-api工作目录，未当RED证据。
- RED：API目录 .venv/bin/python -m pytest tests/aip/test_aip_eval_subject_proof.py -q，collection ModuleNotFoundError；日志/tmp/aos-subject-envelope-red.log。包装tail返回0不等于pytest成功，collection错误明确记录。
- 首轮专项+原v1签名+阶段决策78 passed/5.83s。复审修正原阶段词汇，补严格引用整数类型/三阶段测试。
- 最终同范围102 passed/7既有warnings/5.55s/pytest exit0；命令和日志/tmp/aos-subject-envelope-final.log。
- git diff --check退出0；自动化TOML回读已包含两项授权和严格blocked门。
- 合同绑定原query/subject字节hash、生成Attempt/AgentRun/request、阶段/tenant/规则/安装等；改任一来源hash变化；naive cutoff、缺项、额外执行标志、bool/float/string引用版本、model_copy绕验证拒绝；原字节不trim，同UTC时刻canonical一致。
- 无新增路由/迁移/DB访问/Secret/Provider/Host动作，无UI变动浏览器不适用。pytest使用其标准隔离环境；fixture协议证据不冒真实业务验收。
- 待做：双身份独立subject用途签名、当前issuer/revocation读取、原Owner来源/评测意图/持久writer/阶段消费者、Handoff；Model评测用途串行实施。不再以这两项待用户裁决为阻塞。
- Goal已实读active（用户恢复），未由工具修改。严格blocked规则写入现有aos-2并回读；仅整体穷尽安全路径且同阻塞连续至少三轮等条件才可设置。

final日志SHA256=259bd8e9e5f954a7342c251c66c8f9b6961330c1c4fe7576196d677e8e84ffce
