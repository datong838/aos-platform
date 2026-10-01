# Subject双身份签名验证

依据已批准GW-b §3/4，前序2457fa95完整信封；AOS-001074。Rules：m1单写、AGENTS、aos-engineering-delivery。用户确认实现/隔离验证已有效，不再待裁决。当前库/Provider/Host禁入不变。

新增aip_eval_subject_proof_authority.py：独立subject-review issuer用途、source-witness与judge证书/收据，复用asset_registry.signature的TrustRoot/FrozenTrustRootProvider/verify_ed25519；独立canonical域，不改原v1。证书绑定租户及精确生成Skill或Judge；source只见证原产物，不宣称执行Skill。收据绑定完整envelope hash；Judge再绑定source receipt hash和严格bool结构结果/detailCode。稳定ID绑定tenant/EvalRun/case/envelope/purpose。校验当前根/身份撤销、证书/根在签发结果时及当前有效、未来时间/倒序拒绝；不同身份与解码后不同公钥。输入反序列化重验，model_copy不能绕门。返回已验证结构结果不授予业务权限。

新增test_aip_eval_subject_signature.py：真实临时Ed25519测试密钥正向、双份正文/不同tenant或安装代次防串用、source替换、相同key/identity、根用途/撤销/过期、错签名、bool强制转换、future时间、判失败保持false。测试不是正式客户身份或Owner证据。

验收：先RED缺模块，专项+完整信封+原v1签名回归，复审canonical/identity/domain与时间；落verification、精确commit/上下文。后续必须通过当前持久issuer/审批/撤销Owner读取并接Run/Report生产者和消费者；本纯验证器不能靠caller roots宣称生产authority，更不能停在helper当首链完成。
