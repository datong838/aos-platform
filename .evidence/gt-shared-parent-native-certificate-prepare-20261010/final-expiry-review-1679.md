# AOS-001679 专属最终到期与独立 fresh 邻接复审

Rules与方案：231，final-expiry-plan-1679.md，现有Task9/10及Task3 scoped Lease。产品源码无修改，沿用R11十二份源码精确hash；纯337结果沿用samehash最终已过验证，不为计数重复执行。

R12漏实验夹具，未进入风险/到期专项，整节点失败；R13真实前四次成功及第五次拒绝，测试错误期望legacy文案，整节点失败。两次原实验只读对账，表不存在或零，证据保留。R14修正现有v3精确文案，包装外断言四次成功、第五次拒绝、真实时间跨证书有效期而未到Root/Request期限，同caller保存点Manifest缺失与外风险INTRANS。钩子仅在第四次原validator成功后真实等待，产品自行读final clock，第五次原validator实际拒绝；没有checked_at参数替换、时钟mock或旧证书/原审批延长。最终到期必要门通过，证据独立读回风险ABORTED/九表零/十二hash一致。

R14后续原审批真实到期CAPACITY_JUDGE_CURRENT_DEADLINES_REQUIRED，整节点仍FAILED，不能以专项成功改写整节点结果。R15使用独立新库、新Source/Root/审批/证书，运行原完整R11正向及重放/canary/直呼负门/COMMIT拒绝节点；最终结果与独立ACL/SQL/hash读回另见result-r15.json及independent-core-readback-r15.json。不得把R14专属终止与R15fresh正向说成同一原件窗口。

风险边界：未做可见已发布身份的正式撤回/竞争，未通过非native caller/旧域独立矩阵；实验Root bootstrap信任、final joint/WALACK和正式经营首链仍待正式门。Task9/10 ACTIVE无完整Delivery，Host/worker/Provider关闭，正式库只读，不push。Prime旧UNKNOWN与历史两摘要beforeimage未恢复，均未重发或私改。

最终读回：R15 1 PASS146.76秒/8warnings，独立库aos_test_ba3c980424e4_ti4_test；原风险ABORTED/九表0、四函数准确正文owner/path/PUBLIC0、原C两Owner封闭ACL、Model直接C/schema与runtime委托false、十二hash一致。两组必要证据收口，完整业务权限与Task Delivery仍未完成。
