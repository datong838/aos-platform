# D01同事务输入读取器

2026-09-11，基线9040e237，AOS-000573。受信接收/执行的前置接续：现有独立Owner读取器不能替代运行清单绑定。

新增 `services/aos-api/aos_api/ecommerce_analyst_portrait_inputs.py`。显式conn/scope/run/actor/current now/source limits；类型化每指标QuerySource请求，固定window/cutoff。运行必须是同租户D01并声明Method、全部MetricDefinition、EvalContract、全部QueryResult和EvidenceBundle精确版本（按现有postgresql引用authority约定）。先验证完整唯一inventory，再同conn读取当前权威、正式L3材料和Query，统一截止，整批大小限制，复用完整portrait_prompt验证返回输入。相同Bundle只能在不同指标间以相同正文重复引用；不能借重复计数增加方法源数。无Provider、无提交、无业务ready宣称、无新HTTP入口。

新增对应测试，验证同连接Owner调用、缺清单/错scope/错skill/重复metric/不同Bundle正文/材料超限拒绝及固定prompt输入一致。复用既有实PG各Owner测试，不伪装新增纯测试为真实经营执行。下一波Receiver与原始Artifact/Receipt接续；正式质量、对账及真实连接仍独立门禁。
