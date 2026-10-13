# 八台 root GET 读取接线接续方案

Rules：用户 AGENTS.md、仓库 AGENTS.md、aos-engineering-delivery、231串行主计划与双侧增长产品方案、20261013完整交接；先方案后编码，单m1写者，最小变更，保护dirty，经营首链独立验收。

## 1/8 上位复习与接管事实

新写者 codex-01a13484-f019-7d82-94ce-812396db9124。旧写者已正式候选Delivery停工，原候选Lease释放。完整Goal已支持入口建立active；同一aos/aos-2迁移并回读到新thread，原频率/名称/通知偏好保持。Authority AOS-002012，全部强投影CURRENT，memory validate GREEN。m1 d97c4bae06e211a230efc2786eab642349fd3d9d；交接dirty清单逐项相等，两候选文件SHA一致，66日志及独立复审消费复用，不重跑已交付验证。

原PG容器84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c，原权威卷aos-qyh-history159-prepared-data-20261011，18446；启动03:36:19Z。API58363/18080 cwd冻结ceba8ba4；Web58523/18434存活。最新完整重启未验收；全库指纹与页面没有在此核验中重做。39历史Lease保留；parent维护范围未归属转移，不在本Task改写/重启。

## 2/8 文件与接口计划

本Task qyh-eight-root-get-wiring-successor-20261013，正式Receipt/Lease当前新owner，作用域与原39 Lease无重叠。

- services/aos-api/aos_api/routers/ecommerce_workshop.py：新增独立get_ecommerce_workshop_read_catalog/ReadCatalogDependency，仅精确8 root GET替换依赖；其余GET、readiness、POST及执行门不变。
- services/aos-api/aos_api/ecommerce_workshop_read_catalog.py：复用已交付候选，只有必要factory适配才追加；legacy错误、disabled、原签名/角色/租户/marking/撤销/DataScopeGrant exact不变。
- services/aos-api/tests/test_ecommerce_workshop_read_http.py：HTTP-specific RED→GREEN；当前安装候选授权的8 root读取，原POST/辅助与错误不放宽，无身份/跨tenant/撤销/缺scope拒绝。
- .evidence/qyh-eight-root-get-wiring-successor-20261013：接管验收、committed helper递归审计、RED/GREEN、原生/浏览器、冻结复审与交付证据。不得改旧证据或parent checkpoint。

输入：当前签名selected installation ACTIVE5 + exact lock/角色/每个声明DataScopeGrant；读取AOS保留数据。输出：原业务read-model/真实blocked或unknown；不伪造runtime ready或数据，不造Run/零成功。

先完整追踪Media.read→reader/lifecycle/publisher._compose/cumulative及其store helper，Operations.read→authority/object/inventory/aftersale/case_store。读取git HEAD中的dirty依赖，不能工作树版本混入新启动包。方法/call提取不是无副作用证明；逐个看查询及helper、连接构造和Provider/Source边界。如根路径存在未审计写/网络则不得接该route，登记缺口继续其余安全步。ReadCatalog factory复用installed原构造，不改legacy谓词。

验证：独立HTTP RED、最小实现、专项/原HTTP相邻累计；正常SCRAM角色当前库只读与无身份/canary；最新同卷重启需单独parent归属对账后原支持路径；原owned CDP9244 SPA八页真实读取，不reload、不触动别人的tab。原POST/执行与辅助GET不得获新门。再方案代码一致性、自洽/风险及独立Prime冻结复审，合法消费，Delivery/精确m1提交/Authority和Prime同步，立即下一登记波。

风险与回滚：readers潜在隐式写/网络、readonly unknown被误解释、dirty污染冻结；以源码递归审计+DB只读约束和真实数据验收控制。回滚限本Task确切新依赖注入，不reset/覆盖dirty、不删数据/卷/历史Lease。经营链、预算真正生效和发布仍待独立证据。

## HTTP RED具体合同（编码前补齐）

内容审计见read-audit-findings.md。8root范围精确为/views/{task-cockpit,operations,content-campaign,creator-growth,media-studio,analyst,price-governance,customer}。新增HTTP测试用安装读取门和legacy门独立拒绝哨兵，实际请求证明root使用新门并传递真实principal的tenant/roles/markings；辅助GET、module readiness仍legacy；路由整体遍历证明任何POST/其他GET没有新依赖。认证401及未知query400保留。此层fixture不是原生/真实经营证据，安装签名/scope adapter已交付验证不重跑；正常读取正向需后续native/browser。

兼容复验修正：factory必须用Depends原legacy入口，不能直接调用以绕开原HTTP依赖覆盖。安装factory延迟到legacy AssetNotFound之后才构造，确保旧legacy成功时不受未配置/损坏selected配置影响；不得缓存安装结果。这是已有成功legacy保持的必要实现，追加factory专项证明错误不回退、成功不触发安装构造。

## 正常角色/最新运行验证与维护交接（2026-10-13）

依据当前用户明确正式移交、原写者受支持只读回复确认停止施工与新唯一写者、HEAD32bd509/Authority2013/原volume及进程核验，原parent qyh-full-system-restoration-20261011没有Delivery。通过memoryctl.complete_task写准确HANDOFF_BOUNDARY_ONLY_RESTORATION_INCOMPLETE Delivery释放该parent Lease，不假扮原owner续租，不按TTL清锁、不声称整体恢复完成。current159-maintenance等其余原Lease继续保留。

另登记qyh-restoration-successor-latest-restart-20261013，新owner负责原parent证据/实际原权威卷及API维护、独立新证据目录和已验证启动脚本范围；它与本GET Task范围不重叠。先新的私有Git archive冻结HEAD32bd509（不复制任何dirty/凭据），原guard只支持parent下source报告，使用独立新receipt stem、existing intent/result先只读对账。正常SCRAM/无SUPER/BYPASS三个原角色只读检查当前installation与8module/8root DTO，不造Principal或运行审批；真实浏览器身份仍原OIDC。

重启前只读原volume/container/cluster/schema/全表指纹、现有process cwd/ports及零执行窗口；schema161当前一致则不迁移、不重跑备份恢复施工。核已有完整恢复演练/第二备份证据并当前摘要回读；若需迁移才建立新独立备份/恢复/逐步演练。先PG同容器同卷重启，进程结果未知只读poll，不重发；然后精确PID/cwd停止旧API/Web并通过原supported guard启动最新冻结API/Web，保留OIDC、selected公开签名根、READ ONLY和执行OFF标志。不得用原固定40434/ceba旧prepare脚本重跑。

具体新文件均在.evidence/qyh-restoration-successor-latest-restart-20261013：plan.md、只读指纹/角色验证工具、fresh restart intent/terminal/public receipt、private固定代码快照的摘要证据、浏览器GET真实结果。需要生产script修改时先追加方案和专项RED/独立review；目前复用原supported脚本无production更改。所有新执行均有新一次性intent，已存在或不明终态先对账，禁止旧安装/HBA/Host维护、未知预算模型request、旧12Run、商城源/Provider。
