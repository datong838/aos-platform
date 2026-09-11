# 正式文字产物进入评分输入

2026-09-11，基线c3ce8ea0，AOS-000573。修复文本subject仅metadata、实际target只收到Suite样例的缺口；不更改旧媒体/普通Eval。

修改 services/aos-api/aos_api/aip_eval_runner.py：text subject必须由frozen exact合同声明subjectKind=agent_text_output且subjectInputMode=text-envelope-v1；在每个case目标执行前，经已有受权ArtifactResolver读取原文字Artifact(ref type agent_text_output/r1/原sha)，要求返回确切引用、str正文、<=2MiB、UTF8原始SHA相符。构造固定输入schemaVersion=aos.eval-text-subject-input/v1，subjectArtifactRef、subjectText、caseInput三项，原Suite case作为评分标准输入，不替换或伪造原文。每个case独立新输入，target变更输入不影响后续case；失败沿现有Run失败路径，无Report。普通Eval与媒体仍传原caseInput。报告仅原有hash/计数/metadata，不保存正文。

新增 services/aos-api/tests/test_aip_text_eval_input.py：一次性完整PGclone安装012后，真实Task/Step/Artifact原文、EvalRegistry/Run/Report执行；合同resolver为明确测试替身；target实际收到同hash原文，正文篡改/引用错配/无权读取/超限均拒绝且无通过报告，未声明协议拒绝，旧普通Eval继续原输入。不会调用外部Provider或主库写入，非真实商家数据验收。
