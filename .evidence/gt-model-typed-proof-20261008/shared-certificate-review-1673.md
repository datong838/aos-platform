# v3准备态证书签名必要门复审

基线085e4097f，AOS-001673。产品仅修改services/aos-api/aos_api/aip_model_eval_execution_contracts.py，新增72行四入口；旧39个类/函数AST全部未变。先行计划shared-parent-certificate-domain-plan-1673.md与实现一致：独立v3域，全准备态描述hash+原风险hash+原caller xid/pid+完整manifestHash+原申请/新Judge目的hash+案例purpose/leg/candidate/key/Issuer区间。无allocation或每腿金额；不触及DDL/迁移、正式库、Provider、运输、COMMIT或权限。

纯验332 PASS（1.22s），psycopg.connect全禁止；真实Ed25519四leg及旧域拒绝，完整描述重hash后的identity/Intent/joint变动仍不可复用旧证书，错误根/签名/撤回/到期/非法bool/申请hash拒绝。纯fixture明确从历史描述复制并换实验新公钥重新hash，是synthetic pure，绝非原持久化当前身份。

native R3完整原节点1 PASS（118.64s，8个既有warning），独立fresh Source与新100秒批准、原2case4leg/原规则和请求截止不改，先设置真实实验公钥再生成实际风险和完整描述，后真签四证书。DB aos_test_5b5aea11eb1d_ti4_test@7694680278363095064，独立只读回读xid aborted，风险/完整描述/debit/Intent四表0，Source1，runtime表SELECT/INSERT false，冻结产品hash匹配。公钥/签名可核；私钥仅内存。无UI变更，浏览器不适用。

R1路径退层错误导致辅助库加载失败；R2签名四证书/提交拒绝与独立ABORTED/0通过，但相邻旧路径缺第四个original_source_plan_fixture_r1.py而整节点失败；R3补齐原辅助文件于新目录后全节点通过。原失败日志/结果保留，不用R3覆盖R1/R2。旧50秒审批过期样例、两个事故前实验摘要字节缺失仍保留限制，未恢复或改写旧原件。

风险和未完成：root是presented实验root，无可信bootstrap/provenance/current Issuer原件，executorsAuthenticated/issuerMetadataCurrent/executionAllowed全部false。签名验证者显式输入时刻与撤回集合，不是权威读者；准备态哈希亦不能证明DB原件。Task仍ACTIVE，不交Delivery，不宣自然首链。下一登记候选优先v3独立identity/certificate私有绑定（复用原global identity_epoch/withdrawal但不扩旧v1/v2触发器），同snapshot核当前根/证书/身份原件；actual token/最终joint依真实输入和严格WAL/ACK语义，不猜权威。Prime unknown请求不重发，当前局部ownership缺口不扩大停工。
