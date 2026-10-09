# 原 Source 全套首门诊断与最小测试兼容修复复审

Rules：用户 AGENTS、AOS工程交付、231、原Source S01–S20；唯一线程写者。基线463b466ee2b0aea169894f7cf141d13a323ad3e8 / AOS-001634。

全量收集101函数，初始381节点，首测试显式shared/distinct后382节点。全文件选择使用maxfail=1：r1首门42883；r5脚本BusyBox df setup失败；r6四项通过后原Owner首fault重复安装失败。全量未执行节点仍待验证，收集不等于通过。

精确修改 services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py：第一缺失原文测试依赖原受控完整public fixture，同一原生caller和签名数据组，两布局分别独立库；合法prepare阳性对照回滚，再用合法permit单独测试缺失原文22023，保留SCRAM/Python原checker/审批计数。共享withdrawal辅助函数改为审计a0v157已永久安装函数，完整定义/ACL/lock不弱化；原rollback后零函数断言改为永久三个函数且完整审计。方案先更新原Source Task plan，原fixture6/1差异不提交，产品默认私有安装不改。

r3 distinct混用shared命令的新增测试接线错误原证据保留，改为从同一fixture读取actual_command；r4两布局2pass27.77s。Owner r7完整15故障参数pass30.23s，其helper/Owner函数与最终输入一致；其余8原helper调用者加首项两布局 r8 43pass1fail105.67s，末尾旧rollback数量预期错误修复后，r9完整44pass101.99s，无skip/xfail/deselect。不得把分轮结果说成完整382项一轮绿色。

独立verify_final.py对最终七文件精确hash、三个保留测试库cluster、零Source/publication残留、角色NOLOGIN且无高权限、临时公有接口撤销、occupation零/不存在、完整原函数定义/ACL/lock审计及31旧容器ID/启动时刻/挂载/端口进行只读复核，全部符合。44节点使用三个库（两入口独立库，withdrawal共享一个原session库），不声称44独立库。原r1、r6失败库只读诊断保留；无未知效果重放、删除保留库或真库变更。

一致性与风险：此交付仅bounded首门诊断/最小测试兼容修复，不交付原Source Task；全Source剩余节点、实际最终COMMIT wall-clock已过期仍提交的真实反例、完整正式首链均未闭合，独立模型review无PASS。浏览器无产品界面改动不适用。Goal保持active，不修改其私有存储、不push、不重启系统。后续优先原完整套件未执行首门，在2.5GB磁盘保留门内分波；容量不足只限制创建新库，继续已登记安全调查。
