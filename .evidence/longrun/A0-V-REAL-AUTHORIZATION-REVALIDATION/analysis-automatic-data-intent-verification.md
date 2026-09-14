# SC4-5d1 自动首装数据意图

2026-09-14；基线b3509ee3；m1单写、不push。

AnalysisDataRequirementPreparation增加完成前/完成后自动入口，不接受逐事件request参数。通过当前安装configRef复用原configuration reader和来源Owner授权，读取原当前预算版本；按原cutoff前30天、全店Profile、严格质量与不降级、安装markings、源策略freshness、预算日上限、源/预算截止较早者形成请求，复用原sealed数据Host及稳定key。

这只是需求预算上限，不是余额、价格、预留或执行许可。固定首装口径在当前服务端代码，尚未声称可任意配置业务窗口或已纳入新签名领域包。手动入口保持兼容。

验证：15项数据需求测试（含5个新自动用例）、专用恢复、原当前配置权威合计40 passed/7既有警告/33.71s。实际隔离PG内创建/重放原需求、完成事件入口、配置/预算读取失败无需求、预算变化不覆盖原请求均通过。自动用例的配置/预算读取为明确fixture，实际DataRequirement/Run及sealed写路径真实；原配置权威由邻接测试验证，不当主租户全链证明。首次红测3项缺入口，1项测试时间精度错误已修正，不把夹具错误计业务缺陷。

AR2 1908扫描/187分类/93迁移，五类错误数组空；memory GREEN1102/1084/2702；diff-check通过。无主库改动、部署、远程采集或模型调用。

下一SC4-5d2：现有ecommerce_product_event_worker.py通过原analysis服务接入自动需求；必须处理原START已提交但需求未提交的重试，不提前ack事件、不重复需求，原手动服务保持兼容。之后受控12类采集与原Outbox实际补齐。
