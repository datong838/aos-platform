# W5CB4 E17-s3b｜原 Logic/Route/Policy 发布来源替换文件级方案

## 上位与精确依赖

- 231、56/64、E17-s2c 要求 Skill 的 `logicRevisionRef`、`modelRouteRef`、`runtimePolicyRef` 由原生产者发布，并以精确版本/哈希消费；E17-s2c 的这三项仍为测试授权夹具。
- 默认 `PostgresSkillLogicPublicationAuthority` 在同一事务联 `aip_logic_graph_revision` + `aip_logic_publication`；原 `LogicPublicationStore.publish` 需要 immutable Graph revision、当前 Graph head、成功无生产写 dry-run 和原 Eval evidence，不能直接插 `aip_logic_publication` 当正式生产。
- 默认 `PostgresSkillPublicationRouteAuthority` 读原 `AipModelRuntimeStore.get_route/get_policy` 并要求 active、kill-switch=false 与 route exact Model Eval Gate；原 `publish_policy` 又要求 Network/Guard/Governance Policy，原 `publish_route` active 要求 Model Eval Gate。Model Eval 原 Runner 仍硬拒，不能用 Skill Gate 代替 Model Gate。

## 文件级次序

1. `services/aos-api/tests/aip/test_aip_skill_publication_service.py`：将 E17-s2c 正向链逐项换默认真实 authority；先 RED，预期明确缺 Logic publication，且新 Skill/Receipt 不增加。再沿 `tests/test_aip_logic_publication_store.py` 的原生产者 fixture 追 Graph/dry-run/Eval来源；只在真实原服务完整可构造时接正向，否则保留精准阻断。
2. Route/Policy 同理，先核 `tests/aip/test_aip7_model_runtime_store.py` 原生产者与 Model Eval Gate、Network/Guard/Governance 依赖；不得直接 seed active Route/Policy 或使用 `_ReadyRouteAuthority` 声称原生产者通过。若 Model Eval Owner 缺，单项失效关闭并转独立可做的 Logic 或配置来源代码项。
3. 只有 RED 暴露明确生产代码错误才最小修改 `aip_skill_publication_service.py`；否则本波以原服务合同、隔离 RED、依赖图和正确分类收口。专项/相邻回归、浏览器禁入、verification/Receipt/Authority/Prime 与精确提交。

## 界限

当前真实库只读、Host/worker/Provider关闭；不读商城源、不手工 Run、不重放旧12Run、不写 dev-org、不 push。Mock/test-only 正向仅证明代码局部，不计当前正式发布。
