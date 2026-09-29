# W5CB4 BG-00w｜Eval 双 purpose 签名执行证据纯验证方案

## 入口与风险

BG-00v 的正式 G2 producer/Target/Judge/Receipt 合同已只读收敛。现有 `JudgeRevisionRef` 只有精确引用，`TargetExecution`/`JudgeExecution` 是调用方自报；`asset_registry.signature.verify_ed25519` 只给出密码学原语，现有 bundle trust root 不能作 Eval issuer。当前 G2 signed placeholder 是 BLOCKED，Skill Runner 两入口和 E2/发布/Binding 继续失败封闭。此波不新增数据库表，不开放生产 Skill Run。

## 文件级最小实现

1. `services/aos-api/aos_api/aip_eval_contracts.py`：增加严格的不可变 `EvalExecutorCertificate` 与 `EvalExecutionReceipt` DTO。证书绑定 tenant、purpose(target/judge)、exact executor ref、独立 Eval issuer/key id、executor public key、带时区有效区间及 issuer 签名。Receipt 绑定 tenant、run、suite exact ref、case、purpose、证书 hash、exact executor ref、输入/输出 digest、Judge 的可选 expected digest、actual digest 与 verdict/detail、发生时间和 executor 签名；role shape 与带时区有效期先做字段约束。所有签名字节排除自身，以规范 JSON 和显式域标签参与签名。
2. 新增 `services/aos-api/aos_api/aip_eval_execution_authority.py`：纯函数从**独立 Eval issuer root** 验证证书签名/有效期/撤销快照，再用证书公钥验证每个 Receipt；要求双证书不同 purpose/身份/公钥，同租户、同 run/suite/case、exact target/judge、目标输出 digest=Judge actual digest、expected digest 精确、输入 digest 精确。Receipt ID 由 `(tenant,run,case,purpose)` 确定，返回 claim hash 给后续持久唯一键使用。缺 issuer root/撤销快照一律拒绝。复用 Ed25519 验签算法，签名根类型加入 `eval-execution` purpose，无法直接把 bundle root 配置传入。
3. 新增 `services/aos-api/tests/aip/test_aip_eval_execution_authority.py`：先隔离 RED，测合法签名对及租户/跨 purpose/错 ref/输入输出/签名/过期/撤销/重放 claim 的负例。测试自生密钥只证明纯合同，无业务授权。Runner/E2/发布/Binding 相邻回归确认默认禁入未松动。

## 边界与验证

本波不注册任何真实 Eval issuer、不读商城源/当前库业务行、不写当前库、不迁移、不启动 Host/worker/Provider。纯验证结果不是正式执行 Receipt 持久权威；下一独立波才接持久身份/撤销/唯一键和 G2 Owner/内容来源。专项与受影响累计、编译、diff check、签名 API 当前代码预检；无 API 产品路径改动时不以页面 HTTP 200 充业务验收。缺正式当前 authority 时 Skill Run 继续拒绝。
