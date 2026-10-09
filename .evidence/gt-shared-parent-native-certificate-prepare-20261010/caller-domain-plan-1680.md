# 非原物理调用者与旧签名域必要负门

Rules：231、AOS-001680、Task9/10与Task3合法同owner Lease、m1单写、正式库只读、独立fresh签名实验，未知结果不重放。

登记候选一：同合法SCRAM occupation身份/同Runtime/同租户/SERIAL/UTC的另一真实物理连接尝试原caller风险description及证书；另同原caller给v3 claim签署v2域（正确实验Root私钥有效签名），证明真实v3入口拒绝旧域而非仅bad signature随机字节。依赖现有完整R15与已授权Model隔离实现，不依赖正式Root/Host。候选二：可见已发布identity撤回/竞争，需要合法发布头及竞争协议，当前samecaller暂存未COMMIT不能假称外writer可见或靠TTL删除。先选一。

文件目录仅本Task `.evidence/gt-shared-parent-native-certificate-prepare-20261010/native-r16/` 的helper/driver和本方案、Task3已授权shared-native-caller-domain-1680-r16前缀。产品/现有测试源码不改、十二hash保持；现有Source封闭C ACL/角色授予不动，实验密钥仅内存。

另一连接使用原fixture params，不复制或输出密码；显式require_auth SCRAM已有参数，读actual xid/pid/session/role/isolation/timezone/scope。与原xid/pid不同，同身份和tenant，不修角色/表/grant。其事务仅尝试原SQL入口，要求严格SHARED_DESCRIPTION_RISK_ORIGIN_REQUIRED（查询当前caller原风险未找到），包装外硬断言，不以权限错误代替原caller绑定。窄reader随后要求MANIFEST_REQUIRED，无暂存；另一事务rollback，不Commit或写第二Task。此连接仅隔离负门，不是第二施工写者。

旧域：原v3 envelope schema、原claim/description/caller/hash/key/interval不变，替换签名输入domain v3为v2，用同原RootKey签署；在内存先真实Ed25519验证v2消息成功、v3验证InvalidSignature。原caller当前SQL入口严格23514 SHARED_CERTIFICATE_SIGNATURE_OR_TIME_REQUIRED，savepoint rollback后同xid/pid/live以及Manifest缺失。读取PGclock确保仍在证书/Root/Request窗口，不能把时间失败算域失败。独立fresh证书用于后续完整Python与相邻原完整节点，无旧窗口延长。

验收：两种负门实际原错误及caller事实、正确旧域签名/错误新域、clock界内/原件hash、保存点清理。之后完整native及独立READONLY风险ABORTED/九表0/四函数owner/body/path/PUBLIC0/原C ACL/十二hash。不把负门与实验Root/测试当正式首链，不Delivery，失败保留后修复。

AOS-001681复审纠正：R16 raw时间+00:00与canonical签名Z存在额外差异，因此保留R16旧域密码学与SQL拒绝事实，不声称仅域因果全通过。新的native-r20规范原件，先同caller实际v3 SQL四项正向/保存点rollback/manifest缺失控制，再仅替换签名为同payload旧域签名，前后时间界内及准确拒绝；之后独立即时新签名全Python与原邻接。不改产品。两实验与r19不得并发，共用隔离cluster的occupation fixture角色。
