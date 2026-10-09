# AOS-001678 本波复审：真实身份版本重放及边界

Rules：231、现有同 owner Task9/10 Lease、最小修改、正式库只读。方案见 next-wave-1678.md；本轮仅修改 reader 的 SQL identityVersion 读回与 Python 正整数校验，以及同风险事务验收 helper。其余 Source、时间窗口、权限、角色、签名和产品错误包装未改。

R9 实际完整 native RED 93.50秒：原件读取后缺 identityVersion。R10 1 PASS141.08秒，版本四项2→2，租户canary与runtime直呼委托拒绝；R10测试哈希绑定保存的真实beforeimage，不冒称最终版本。复审补上包装外 replay_proofs 恰一项、版本前后相等及外层实际xid/pid/live状态硬断言，防止产品 except Exception 包装吸收测试 AssertionError 而伪PASS。R11最终测试 1 PASS138.76秒/8 warnings；pure-r6 337 PASS1.30秒、数据库连接为零。

R11独立 READ ONLY 读回：DB aos_test_f2e224d60b94_ti4_test，指定隔离 cluster7694680278363095064；风险实际 COMMIT拒绝且 xid aborted，预发布实验Root xid committed；九张风险/暂存元数据表0。四个SQL函数正文、owner、固定search_path准确，PUBLIC EXEC0；12份最终冻结源码hash全部匹配。原C验签ACL仍仅原两个Owner；Model直接C/schema与runtime委托EXEC均false，Issuer窄委托true。正式库、Host、worker、Provider无操作。

重放使用同caller持久certificateBody的精确原件，四项身份版本[2,2,2,2]前后不变，全证书元数据不变；canary严格原错误42501，runtime直呼委托权限拒绝，恢复后caller与元数据不变。重放位于SQL暂存完成后的受控Python故障保存点内，随后实际拒绝回滚、Manifest缺失、外风险仍live；完整Python正向使用后续独立新签名40秒原件，同外风险caller和description。不能宣称重放后完整Python正向仍使用同一短证书，不能延旧证书/审批时间。

Task9/10 ACTIVE，无完整Delivery。非native caller、旧域、撤回、专属最终到期仍待独立矩阵；实验Root bootstrap谱系不可信，final joint/WALACK/正式经营权限未通过。Prime旧UNKNOWN不重发；历史两摘要beforeimage仍未恢复。不把此门、测试、提交或页面200当自然首链。下一安全项为真实证书最终到期终止专项，与fresh相邻正向分开。
