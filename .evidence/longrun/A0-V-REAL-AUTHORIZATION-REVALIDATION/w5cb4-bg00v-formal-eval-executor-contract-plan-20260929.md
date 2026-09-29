# W5CB4 BG-00v｜正式 Skill Eval 双执行身份与 Receipt 合同冻结

## 上位目标与现场

231 首链要求真实安装/来源/权限/预算/审批/产物证据，AIP-4 E1B 的 Eval 是 Skill 发布前置。当前 `solution.ecommerce.growth@1.11.0/content/evals/placeholder.json` 明示 `BLOCKED / Waiting for G2 review / Growth evals are produced by G2`。`JudgeRevisionRef` 只有 id/revision/hash；`AipEvalRunner` 的 Target/Judge 是调用方回调；`aip_eval_run`、`aip_eval_report_revision` 无独立签发/撤销/执行 Receipt。BG-00q/u 已在两种入口的 Skill Run 写入前拒绝，BG-00r/s/t 已在后续消费失败封闭。当前库 `org-org/dev-project` Suite/Run/Report/Gate/Event 皆零行，不能用测试回调/旧 Logic Report 补空。

## 正式正向合同（需 G2 Owner 和独立签发 authority）

1. **内容生产者**：G2 Owner 发布不可变 Dataset/Case Artifact，给出同租户、exact object key/digest、字段白名单、脱敏 Receipt、来源截面与撤销状态。D-wave 只消费已批准的正式制品；当前 placeholder 不可当数据源。BG-00m/n 的 reader 只证明字节核验代码，BG-00o 真实 S3 仍未读回。
2. **两类执行身份**：Target 与 Judge 使用不同 purpose 的 signer identity；每条身份有 tenant、owner/issuer、exact target 或 judge revision/hash、key id/public key、有效区间、revocation event。当前 bundle 的 publisher trust root 专用于 OCI/安装签名，不能升级为执行身份。通用 `asset_registry.signature.verify_ed25519` 可复用验签算法，但 Eval 需独立、可审计的根来源与用途隔离。
3. **每 case 执行 Receipt**：Target Receipt 绑定 tenant、run id、suite hash、case id、输入 digest、target exact ref、输出 digest、尝试身份/时间和签名；Judge Receipt 追加 expected/actual digest、judge exact ref、布尔裁决与 detail code。唯一键 `(tenant,run,case,role)`，相同命令可回读，不同 payload 重放拒绝；未知效果只读对账。Receipt 只存 digest/refs，业务敏感原文留在受控对象来源。
4. **消费与撤销**：在 EvalRun 接受前锁定当前有效身份、Owner 与批准范围；每次执行 Receipt 验签和 exact 输入输出关联。Report/ReleaseGate/Publication/Binding 消费时重新检查身份和撤销与 Receipt 是否仍满足当前准入，不以过去 PASSED 状态冒充当前权威。撤销后阻止新放行，不改写历史不可变行。

## 文件级施工与安全顺序

- BG-00w：在 `services/aos-api/aos_api/aip_eval_contracts.py` 增加纯合同，`aip_eval_execution_authority.py` 加纯验签/精确绑定器和对应测试。默认无当前 authority 时保持 Skill 全链拒绝；测试生成密钥只证算法/负例，不算正式正向验收。对照 `aip_eval_runner.py` 与 E2 消费点列出适配接口，不先开放 Runner。
- BG-00x：若合同复审确认需要持久身份/撤销/Receipt，单独 additive `a0v_112`（或届时线性头的下一号）及隔离 PostgreSQL RLS/append-only/唯一键/重放测试；当前库先做一致备份可恢复和克隆全链演练，在零执行窗口单独迁移，不与本波混合。迁移前代码头不得超当前 `a0v_111` 后仍声称当前实例是最新。
- BG-00y：接 G2 正式 Owner/内容 producer、授权签发者与私钥保管，隔离双身份实际签发/撤销与真实对象 S3 读回，再按正式审批迁当前实例，最后才允许有界 Skill Eval/发布/Binding。预算、Host 与自然首链按 231 独立当前门复验。

## 本波退出和禁止项

只读核当前表、代码、签名 placeholder、签名算法；给下一波可执行文件清单。无代码/迁移/当前业务库写入，不制造签名根、不拉起 Host/worker/Provider、不读商城源、不重放旧 12 Run、不动 230 L0、不 push。G2 Owner、Judge/Target issuer、撤销和执行 Receipt 未出现前，正式正向仍 RED。
