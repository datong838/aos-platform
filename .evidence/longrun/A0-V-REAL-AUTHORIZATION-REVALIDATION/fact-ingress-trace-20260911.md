# 事实输入链定位及规范对象实况

基线abe084f6。执行专用恢复库只读统计，限定org-org/dev-project，ecom_object按object_type聚合=[]，Product.properties字段类型聚合=[]。因此当前恢复库不仅Evidence为空，规范业务对象也为空。未访问上游，不代表上游数据不存在；未输出客户正文或凭据。

源码证据：
- data_requirement_quality_evidence只保存requirement、measurement、assessment，factIds=[]，不是商品正文。
- aip_task_store._insert_evidence调用点为运行控制、TAOR阶段、失败等；record_step_phase把payload包在stepRunId/stepKey/payload中，不会自动建立事实覆盖。
- aip_business_investigation_evidence.BuildRequest要求外部提供supporting/counter Evidence refs，本身仅交给EvidenceBundle builder，不读取源、不生成事实正文。
- ecommerce_growth_runtime_adapters的RESUME_DATA要求已有完整、fresh、frozen的EvidenceBundle，并依required_facts复算覆盖；不能通过把observation/quality的factIds=[]改成业务事实来绕过。
- ecommerce_product_observation_comparison验证源goods_id/site_id、规范ecom_object exact payload_hash与渠道population；源goods_name对应规范title，price对应price，goods_stock对应stock。它输出比较计数，不是商品正文快照。这里可复用字段语义，但不能把比较结果当事实。

下一施工顺序修正：先核查恢复库真实连接配置、渠道/实体绑定与接入执行入口，使真实商品等规范对象恢复生成；随后在可信源读取/映射边界持久化选定事实正文（exact源配置、rows hash、cutoff、范围、用途、marking/license），再构造EvidenceBundle并装配内容输入。需要明确真实新鲜度证据，不能拿read时间当上游snapshot。现有L3读取作为后段保留，不先激活空输入首链。

无代码或业务数据修改、无Provider调用，证据改变下一步实际执行顺序。完整首链、八工作台、连续观察、发布评估未完成。m1单写，不push，230 L0挂起。
