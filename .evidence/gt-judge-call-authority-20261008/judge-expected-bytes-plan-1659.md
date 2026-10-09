# 原独立 Judge 完整 expected 字节绑定

Rules：231、原新purpose Judge合同、Main Owner/原Judge test两个同owner非重叠Lease、m1唯一写者，先方案后实现。当前1659、真库只读，Host/worker/Provider关闭。

候选一Source实际结束协议依赖可信终态不能用commit timestamp；候选二已登记Judge原Target输出/expected字节。本轮先实现后者的expected必要门，真实Target输出持久签名来源仍独立pending。

精确修改 `services/aos-api/aos_api/aip_model_eval_execution_owner.py`（Main原scope），`services/aos-api/tests/aip/test_model_eval_judge_authority_pg.py`（Judge原scope）；新增fixture/runner/证据仅Judge evidence目录。两Task完整不Delivery。复习ModelEvalTargetJudgeExecutionManifest完整原cases/model/rule/approved parents绑定和validate_original_target_judge_manifest同caller原Registry→fee→bucket锁序、原独立批准/expiry语义，不复制或放宽。

新增validate_original_judge_expected_bytes：严格原whole typed Manifest；expected必须immutable tuple且每项exact native tuple(caseId, bytes或None)，完整顺序一次；所有bytes有1MiB上限，若原expectedHash=None只准None，若有hash只准bytes并sha256原始字节逐项精确等于原批准hash。明确声明过的空Artifact允许其真实空bytes hash，不能把空bytes当缺失expected。前后复用whole原caller guard，保留原锁/currentness/deadline。无格式推断、归一化、任意resolver、SQL写/transaction控制、Target结果认证或执行grant。

新fixture只在新root显式probe：先走原治理注册，再以原Registry注册新Suite和冻结新Contract，expected Artifact注册新test-owned引用/原始bytes hash，在原Model申请/独立Checker批准之前完成。旧不可变Suite/Contract/申请不改；原helper副本必须逐字节一致，新expected helper另校验。业务自然来源/脱敏/正式Artifact读取通道不由此fixture证明。

RED：带真实新expected原批准双申请/新Judge独立批准/本caller双hold后，新增方法缺席。GREEN覆盖两cases原始expected bytes；错raw/hash、尾空白、缺失/重复/重排/跨case、mutable tuple内bytearray/列表、额外case/None/过大均实际拒绝；无expected的原default Suite另新库原whole相邻验证None正向及空bytes负门。可用scope/model/approval/rule过期负门继续复用全原矩阵，不能从原whole成功外推新gate已测所有负门。

独立READ ONLY核新Suite/Contract原hash与请求及expected引用、原caller ABORTED、精确whole parent零、执行计数零，另外如实记录原测试独立COMMITTED Judge hold。旧证据和精确helper不变。浏览器不适用。仅必要byte绑定，token/sourceactual-end/Intent/Targetoutput/Judge格式费用质量正式identity仍未完成。

## 相邻 r1 诊断与 r2 修正

r1原default Suite存在另一expectedHash，非无expected；失败在probe输入断言，保留exit1/全库，不归因产品门。新增 registered_judge_no_expected_fixture_1659.py，仅注册全新两cases expected_artifact=None Suite及冻结Contract，发生于原申请/批准之前，不覆盖旧Suite/Contract/Artifact；新run-judge-expected-bytes-adjacent-1659-r2.py用新root/newDB真实原全链。产品Owner和原test不变。独立verifier分别记录RED缺方法、GREEN有expected、相邻r1输入错误和r2None成功；r1未保存xid不声称ABORTED。
