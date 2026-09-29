# W5CB4 BG-00v｜正式 Eval 双身份合同只读核验

方案 `w5cb4-bg00v-formal-eval-executor-contract-plan-20260929.md`，基线 `aos-platform/m1@739bd0d8`、authority `AOS-000870`。复习 231 首链、228 G2、AIP-4 E1B 与现有 Runner/E2/Registry/OCI 签名边界；本波仅收敛设计和下一文件清单，没有代码、迁移或当前库写入。

1. 当前签名增长包 `solution.ecommerce.growth/1.11.0/content/evals/placeholder.json` SHA256 `e90c23c9234793da6f76f82cc78ceddd677ce47c4c6ed7ced8397bb11d0a69c2`，内容明示 `BLOCKED`、`Waiting for G2 review`、G2 是 Evals producer。目录签名来源不能证明 Eval 内容或执行。
2. `aip_eval_contracts.py` 的 `JudgeRevisionRef` 只有 id/revision/hash；`aip_eval_runner.py` 的 `TargetExecution`/`JudgeExecution` 是调用方返回的 ref/value/verdict，既无 signer identity 也无执行 Receipt；BG-00q/u 已在 Skill 两入口建 EvalRun 前拒绝。`aip_release_publication_service.py` 后续对 Skill 无正式 executor 继续拒绝。
3. 当前权威库 `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -U aos_app -d aos_current_preview_20260927 -Atc 'BEGIN READ ONLY; ... COMMIT;'` 退出 0：`a0v_111`；`org-org/dev-project` Suite/Run/Report/Gate/Event `0/0/0/0/0`；`information_schema` 中 `aip_eval_executor%`、`aip_eval_execution%` 表为零。未读商城业务源。
4. `asset_registry/signature.py` 的 `verify_ed25519` 能校验签名和当前 trust root，但现有 provider 按 bundle publisher/key id 供 OCI/安装使用；没有 Eval purpose/tenant/Owner/Receipt 绑定。可复用算法，不可复用它的现有正式身份作 Eval 放行。
5. BG-00o 仓库固定 MinIO 镜像上一轮 HEAD EOF，真实 S3 读回继续缺。8080 `/v1/ready` 本波 HTTP 200，只说明服务可达。

复审：合同把 G2 内容来源与 Target/Judge 双 signer、每 case Receipt、重放和撤销分开；当前实例缺任何一项都保持拒绝。下一波只做纯合同/验签器负例且默认关，当前库迁移须另波完成备份可恢复和克隆全链。BG-00v 本身未 RED/编码，不能称代码门 GREEN、正式身份 GREEN 或首链完成。
