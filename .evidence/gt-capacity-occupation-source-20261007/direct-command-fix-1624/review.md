# 原 Source Task 直接命令修复阶段核验

基线 be78533e / AOS-001624。先补原方案，产品仅一行 model_validate(command)，原专项新增三项真实额外字段固定拒绝/合法再读。不修改SQL、Source、认证、权限和期限。

真实原 native 1PASS101.11秒：真实Source/SCRAM/Plan Intent call/root typed正向，三额外字段拒绝、未变命令再读、原完整manifest及实际COMMIT负门完成。独立 aborted/six0/Source1/NOLOGIN/member0/probes0/31旧资源全部核对通过。

原 Source shared/distinct 两布局及静态入口专项3PASS85.88秒，7既有warnings/noSKIP；40权限漂移负门及恢复正向、native reader-first/writer-first JWT跨期、Owner/8认证/5引用/SET、真实签名撤销与writer-first旧snapshot拒绝均复验。独立3保留库、2Source签名/hash/provenance、2真实撤销签名/hash/epoch1→2/currenthead撤销、全部角色ACL和旧profile恢复通过。

审计r1资源库存列表逐字顺序比较失败，但随后只读未发现任何资源字段差异；保留初审脚本及失败记录，改为比较每个完整mount条目的规范集合后通过，不能据初审断言失败推断实际重启。专项运行期间角色临时LOGIN的再次审计未计验收，等待finally恢复后独立通过。

当前产品/原专项仍属先前未追踪整实现：保留本次精确diff与原字节快照，未stage完整Source/epoch-profile实现，原Source Task不关闭、不宣称整Delivery。阶段GREEN不能证明正式首链、真实Judge/费用/Provider已执行。下一步登记完整旧未追踪实现的逐文件交付范围与相邻旧issuer-consumer回归，独立方案/代码复审后再精确提交。无当前库写入、服务重启、其他分支、push或Goal修改。
