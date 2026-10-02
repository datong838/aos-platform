# W5CB4 E17-s2c｜原 Skill 正向签名发布链文件级方案

## 上位复习与当前事实

- 231 主计划、231-3/231-9、56 技能发布台产品方案、64 API/UI 方案要求单条 evaluated→published 经 exact Eval/Gate/Event/Logic/Route/Policy、Receipt/幂等/租户隔离；页面禁止把历史评测当正式放行。
- E17-s1/s2/s2b 已分别接持久双签读证、原 Gate 与最终稳定事务，但隔离测试只分别到 PASSED Gate 或缺侧证禁入。浏览器当前共37条仅已评测、已发布0，发布按钮禁用，工作台无可见业务入口。
- 当前正式身份/Run Owner/writer 不齐、当前真库只读，因此本波仅以临时 `aos_test_*_ti4_test` 证明原生产者和消费者代码正反链，不能改变正式实例。

## 文件级步骤

1. 在 `services/aos-api/tests/aip/test_aip_skill_publication_service.py` 写隔离联测：经原 `AipSkillRegistry.publish_skill` 得 evaluated Skill，用当前 Suite/Run/Report 与独立 test-only Target/Judge 双签持久侧证，经原 `AipReleasePublicationService.derive_gate/publish` 得 PASSED Gate/Event，再调原 `AipSkillPublicationService.publish_evaluated_revision`。assert 精确 parent/tenant/Gate/Event/Logic/Route/Policy、published 修订、Receipt/幂等。撤销、错 Event 不得产生新发布 Receipt。Logic/Route/Policy 本轮沿既有测试授权夹具，**不计这三项原生产者正向证明**。
2. 仅当 RED 暴露生产代码的具体缺口，先读错误和原实现再局部修改 `services/aos-api/aos_api/aip_skill_publication_service.py`；不得放宽签名 proof、当前发布路由、DB 隔离或用测试替代当前正式身份。若只有原身份/来源缺失，则局部记录并转下一已登记研发项。
3. 跑专项与相邻回归、`py_compile`/diff check；只读浏览器状态；复审真实实例与隔离证据的界限。verification、D-wave、01/06、续接文档、Delivery Receipt、Authority/Prime 与 m1 精确提交。

## 输入、风险及退出

输入为原 evaluated Skill 修订与持久 Eval 来源，输出为隔离新 published Skill/Receipt 的同租户签名消费链；真实库无写、Host/worker/Provider关闭、无商城源/旧 Run/manual run_definition/230 L0/push。不能把 test-only 签发材料搬到当前实例，不能靠手插 published lifecycle 宣称通过。若精确正向仍不可构造，保留 RED 与分类证据，下一波优先原 Run Owner/签发生产者，不扩大为 Goal blocked。
