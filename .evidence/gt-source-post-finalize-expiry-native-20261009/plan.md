# 原 Source finalize 后认证到期的实际 caller COMMIT 观察

基线37a2cefe/AOS-001627，Goal官方回读active。候选①原Source最终COMMIT时间合同证据缺口；候选②独立review入口daemon代际失效待受支持恢复。选①。新Task仅本目录及5436原lab新全迁移保留库；原Source/epoch/三legacy依赖Task不关闭、不修改。

原同SERIAL/SCRAM issuer、原签名root/document/两批准/账户/Provider/Evidence、fixture真实OIDC签名20秒JWT（既有Source consumer原测试同样使用此窗口）。实际public prepare→Source独立原key签名→public finalize时数据库时钟必须早于原JWT exp。随后实际等待dbclock跨过JWT exp，Source主体expiresAt须仍在未来，再用原caller实际COMMIT，记录成功或精确原生拒绝；不能把成功自动判安全漏洞，不能把本观察PASS计成签发提交时效保证。若成功，独立事务核真实Source hash/nativeC签名/provenance及原xid committed；若拒绝必须独立xid aborted且Source absent。

两布局shared/distinct；每节点保存数据库UTC/真实PID XID/deadline/Source有效期/hash，不保存JWT或密钥。未知COMMIT结果只读对账不重发。等候分段<=5秒，最长30秒；不mock时钟/不改数据库expire字段。finally恢复旧接口/角色/profile，独立核9?以实际保留库数量为准/旧31资源；不用计划或日志推断DB结果。无需浏览器。冻结现有product文件hash确保无写入，结论仅补原最终提交合同的真实行为，正式首链/Source整体仍pending。

真实r1未加载tests.conftest，业务未开始；r2模型字段误用且新node未命中原注册名单，第二布局复用同fixture DB失败。独立r2全5发行域0/Source无提交，原注册epoch1保留不删。r3只修诊断valid_until及显式调用原bootstrap逐布局全迁移建库/缓存恢复（原registered_database_isolation相同实现），不改产品/注册/DDL或时钟。
