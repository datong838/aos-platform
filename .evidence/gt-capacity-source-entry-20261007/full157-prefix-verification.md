# 完整157原锁前缀实测合同

基线5dbc75ab / AOS-001437。父Task ACTIVE，157/SourceDelivery未完成。

真实原native SCRAM SERIALIZABLE会话中，局部观察原psycopg.Connection.execute；调用原check_native_capacity_supplier_inputs，所有实际SQL/原JWT/身份/审批/Hash/Scope/供应商签名检查正常执行。只记录限定类别、SQL SHA256和预先限定asset/epoch ID，不记录JWT/passfile或任意参数。原函数exact Connection类型及execute identity保持，局部拦截恢复后又读native pg_locks并rollback。

r1原check已成功但分类器错把proposal查询中的membership存在子查询当锁目标，首类别断言FAIL/7.63s；修正为实际FOR SHARE OF p，原request不含SHARE单列普通读取。r2 1PASS7.75s；r3补普通Evidence/build/receipt读取及有限目标ID，1PASS7.97s。保留错前提日志，不改原锁/权限/SQL来制造绿。

两实际布局：shared原fixture一Evidence目标；distinct通过原build/Provider producer新建两Evidence及两Provider、原CandidateStore持久化新account/basis，原Source另提案并独立批准，供应商材料重新真正签名匹配新Evidence/完整Provider集合。account三个Provider输入特意反序，原Guard实际按assetID排序；三Evidence也实际按ID去重排序锁。distinct两正向2PASS11.73s，最终相邻原正向/故障案例15PASS191deselected7既有warnings/noSKIP41.59s。该证据是原issuer程序实际执行oracle，不是新publicationOwner执行或完整SQL157/竞争/最终COMMIT验收。

实际顺序不得统一表排序：
1. 原Source approved proposal FOR SHARE；Source Object/Action metadata SHARE；Source maker membership SHARE。
2. allocation先读原request并锁当前Provider head（Evidence行/receipt等普通读取，不是SHARE）；随后allocation approved proposal SHARE。
3. allocation Object/Action metadata SHARE；再次request/currentProvider/Evidence读取；allocation maker和checker membership SHARE。
4. source组合账户/basis/request原行读取后，三路Evidence按ID去重取得neutral epoch SHARE；完整账户Provider集合按ID锁current head；account/basis Evidence原模型/Build provenance/Receipt读检查。
5. Source checker membership SHARE；两个proposal withdrawal epoch按ID排序锁，普通withdrawal/current checks仍执行。

观察到3次request读取和重复metadata/member/Provider检查，不能随意消掉它们再宣称严格原锁序等价。原Request/Evidence查询没有FOR SHARE，不虚构row锁。epoch函数内部锁的实际效果已有156真实竞争证据，新157仍需全链竞争复验。shared/distinct具体SQLhash/targets/native xid/pid见full157-original-prefix-traces.json。

复审：测试只改原transaction_pg，生产文件和旧正常逻辑未修改；无全局patch残留、无secret记录、无正式DB/迁移/服务/Provider执行或第二写者。diff--check通过。全部test DB保留。

下一直接将该实际顺序装配到完整157：原untrusted command/authentication profile、S01 native issuer/Owner/ACL context，原metadata/membership/approval/currentProvider/Evidence/neutral/withdrawal完整前缀，再S17–20 registry/supplier/window/permit后缀；prepare返回精确原native事务待签bytes，受控signer重验原JWT并签同body，commit严格同session/xid/nativeattempt，真实callerCOMMIT和consumer。最终COMMIT TTL反例仍未解决，不宣称全入口可用，不新增正式权限或关闭SourceDelivery。
