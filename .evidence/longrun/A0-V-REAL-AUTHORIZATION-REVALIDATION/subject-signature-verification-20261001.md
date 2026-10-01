# Subject双身份签名验证

Task AOS-SUBJECT-SIGNATURE-20261001，已获用户设计/实现/隔离验证批准。
- RED：services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_eval_subject_signature.py -q，ModuleNotFoundError，新authority未实现，pytest exit2；/tmp/aos-subject-signature-red.log。
- 首轮新增签名+信封+原v1签名88 passed/5.06s。
- 复审补错域、稳定ID重放、签名时间倒序、根过期缺失、witness伪结果及严格Judge整数版本；最终加原阶段决策，127 passed/5.51s/exit0/无skip，/tmp/aos-subject-signature-final.log。10 warnings包括7既有和3故意model_copy非法类型触发的序列化警告，不影响拒绝测试。
- 实现复用原TrustRoot/FrozenTrustRootProvider/verify_ed25519，不另写密码算法；source-witness只见证原生成Skill来源，Judge签完整信封+source claim哈希+结构结果。双身份和解码公钥独立、issuer用途隔离、当前/执行时有效性、身份撤销、未来/倒序、两种域及稳定ID校验。
- false结构结果原样保留，验证通过不等于业务评测通过；返回值无READY/执行许可。调用者仍须提供真实Owner读取的信封及当前root/revocation来源。当前尚未接持久来源/原生成事件/Report writer/阶段consumer，不能宣称正式产物链或首链完成。
- 测试密钥仅测试身份；无当前库/Secret/Provider/Host/worker/商城源/旧Run动作，未push。无UI变动，浏览器不适用。旧dirty保留。
- 下一波：核对原aip_eval_persisted_authority_reader与ACL，确定subject独立用途的当前issuer/证书/撤销保存与读取来源；优先复用原Owner，additive schema前独立方案/RED，仅隔离库；然后接原EvalRun意图和Report/Stage消费。Model评测用途已授权仍串行实施。

final日志SHA256=1b4bbf8a618a2d19a5a1ab940eda22abe14859554b6e1422f783e77417388fa1
