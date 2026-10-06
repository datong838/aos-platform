# S11 原申请存储门进入实际guard读取

基线05d099d7/AOS-001384。publication及formal-boundary已有Task单写串行；Owner/lease20:00/16:00有效。方案先更新，范围publication_store.py、原action.py的_request、formal PG测试及两Task证据。

CAPACITY_REQUEST_ROW_SQL只读精确正向tenant/id，原整份request_json canonical实际hash=stored=expected、固定REQUEST_ONLY_NO_CAPACITY_NO_START、两个IS FALSE、expires_at>当前DB clock、object恰application/makerSubject、maker string=created_by成立后返回。原_request实际使用该查询；原query后时钟、全部Python存储复核、strict model/tenant/proposalExpiry/window/Provider/Evidence/身份与锁序均保留。原错误码与普通runtime路径保留，没有用PASS/布尔绕过原guard。

RED两项缺常量；首轮2 passed/7.65s。独立复审指出JSON改变造成hash拒绝遮蔽结构测试，已在TEMP故障中同步重算stored hash并更新expected，独立核extra/missing/array/JSON null/maker number/wrong maker。14项原存储单项故障拒绝，双false含SQLNULL；两个原合法内部空格/零宽账户别名重算hash后仍由SQL接受，并经原ProviderCapacityRequest解析。TEMP只计算域，不伪造正式批准，savepoint恢复并最终rollback，不改原不可变记录。

真实isolated Source/allocation formal fixtures、private SCRAM/RLS沿原ref读取实际申请及调用原guard成功；错hash/dev-org/缺id均零行。最终相邻覆盖原request/runtime action/source action/formal boundary/publication/Source contracts：444 passed、7既有警告、188.47s。同一进程终结，没有重发未知效果；固定无网络native verifier由既有fixture核原image/Task/端口。git diff --check通过。

独立route_supervisor只读复审未见范围内重大实现/锁序/NULL问题，确认哈希遮蔽修订解除；最终相邻当时尚未终结，其结论未代替实际测试验收。无页面改动或新HTTP入口，本项浏览器不作为授权证据；未重启服务或宣称live业务已运行。

不新增DB函数/角色/grant/迁移，不改当前权威库/Host/Provider，不授capacity。这个原存储门并非全原生typed application或完整S01–S20批准，fullSource/consumer/COMMIT时间及晚提交归属仍未满足，Task/Goal ACTIVE、无完整Delivery。下一S12沿原account/basis三键wrapper及maker/kind/flags/hash完整核，随后组合原完整动态批准和可信签发，不回退到单hash证明。
