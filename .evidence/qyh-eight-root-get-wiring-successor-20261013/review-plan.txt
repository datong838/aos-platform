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
