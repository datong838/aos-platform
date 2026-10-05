# 容量来源签名文档协议检查点（fullSource ACTIVE）

2026-10-05，m1基线d8d4d521 / AOS-001353；现gt-provider-capacity-source-20261005已登记范围内。

## 实现和真实验证

严格positiveTenant policy/attestation/部署声明/envelope契约：固定purpose/policy publisher，policy绑定供应商签发者与key/rootrevision、计量mode、maxage/skew、有效期和DB/cluster目标声明。attestation绑定supplier/fingerprint/完整Provider exact集合/Evidence/计量上界/观察时间。客户端publicKey/verified/未知字段拒绝。签发者/key字段在已签body内，引用逐kind/id/revision/canonicalhash核验。

check_signed_capacity_documents使用原canonical_json/canonical_hash及Ed25519/真实FileTrustRootProvider一次snapshot；两份签名、root当前性与原rootrevision、supplier/tenant/mode/观察及有效期均核验，command四exactrefs绑定requesthash。输入每次重解析；返回不可变hash及SUPPLIER_DOCUMENT_SIGNATURES_ONLY_NO_CAPACITY_NO_START/executionfalse，不认证JWT、不读原DB行、不验证部署目标或原Owner批准、不产生正式Source或容量事实。

- supplier-signed-documents-red.log：缺新policy模型/验签入口，20 fixtureerrors、70deselected、6.14秒，exit1；这是协议入口缺失RED，不是已实现的签名业务失效。
- supplier-signed-documents-green-r1.log：真实临时trust-root文件、两把Ed25519生成/验签，20passed、70deselected、6.37秒、exit0。负例含wrongkey/伪签名/policy signer替代supplier/supplier不匹配/mode/未来观察/过时/过期/root撤销或过期/rootrevision/ref漂移/客户端key和verified/嵌套construct。语义反例重新签名并更新对应refhash，防止只因旧hash拒绝产生伪GREEN。
- supplier-signed-documents-adjacent.log：四文件174passed、8warnings、125.96秒、exit0；覆盖原候选/真实Source审批/私有SCRAM read核及原trigger/epoch竞争。额外serializer warning来自故意构造bool代替integer的反例，不改变严格重解析拒绝。
- 三文件AST和精确diff whitespace通过，无页面改动；受邀只读route_supervisor复核无本内核重大阻断，提出root部署/撤销COMMIT协调缺口并补入方案。不是独立daemon自主值班验收。

## 完整目标仍待完成

FileTrustRootProvider任意文件/一次snapshot不提供生产信任或事务COMMIT当前性。真实来源必须固定部署root出处并协调policy/root撤回，核真实DB/cluster/角色目标，在同privateSERIALcaller从原批准candidate核supplier/fingerprint/Provider集合/Evidence/计量上界/validity；全域稳定账户/Provider唯一、原子nonexecuting signed Source实际COMMIT、rollback/replay/unknown reconciliation、consumer当前性继续pending。内核返回不能作为跳过任何原检查的授权。完整Source/formalBoundary/b90任务保持ACTIVE。

当前真库、Host/worker/真实Provider/Secret/商城源/旧12Run/manualrun_definition/230L0/未知外部重发/外部效果均未操作。仅完整Source落地后继续共享occupation/Intent与完整八facts实际三写COMMIT/API/ToolBinding/自然经营首链/八工作台/观察发布。
