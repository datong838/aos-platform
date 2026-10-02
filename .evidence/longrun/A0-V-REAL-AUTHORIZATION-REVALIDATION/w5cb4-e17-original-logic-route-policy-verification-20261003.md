# W5CB4 E17-s3b｜原 Logic/Route/Policy 来源禁入与依赖图验证

## 新增可复核证据

- E17-s2c 的隔离签名 Gate/Event 正向后，用默认 `AipSkillPublicationService` 再发布新幂等键：缺原已发布精确 LogicRevision，抛 `skill publication requires an exact published LogicRevision`；再仅注入既有 Logic 测试授权夹具而保持默认 Route authority：缺当前路由，抛 `skill publication model route is unavailable`。两次都不能创建第二张发布 Receipt，旧成功 Receipt仍1。这是明确的原权威负例，不是原生产者正向。
- 专项1 passed；相邻 SkillPublication/ReleaseGate/E17-s1 组合24 passed、1 原有 xfail，`py_compile` 和目标 diff check exit0。只在 conftest 临时 `aos_test_*_ti4_test` 中写隔离签名行，当前真库未写。

## 原生产者链与未解依赖

- Logic 默认消费者需 `aip_logic_graph_revision` 与 `aip_logic_publication` 精确联接。原 `LogicPublicationStore.publish` 要求当前 Graph head、不可变修订、成功无生产写 dry-run 与 Eval evidence；现有 `test_aip_logic_publication_store.py` 正例用 `FakeEvidenceReader`，不能作为正式原 Eval 生产者验收。
- Route/Policy 默认消费者需原 `AipModelRuntimeStore` 的 active Route/Policy、kill-switch=false、route exact Model Eval Gate。`publish_policy` 又核 Network/Guard/Governance，`publish_route` active 需 Model Eval Gate；Model Eval Runner 当前硬拒。直接插 active 路由/策略或把 Skill Gate 代 Model Gate 均越权。
- 本波未改任何生产代码，未完成 Logic/Route/Policy 原生产者正向替换；继续以局部门禁禁入。下一步优先挑出不依赖缺失 Model Eval 的 Logic 原 Graph/dry-run/Eval 读者或八配置合法生产者的独立缺口，按文件级方案/RED 施工。正式身份/Model Eval 到位后再合并正链。当前真实库只读、Host/worker/Provider关闭，首链 pending，Goal active。
