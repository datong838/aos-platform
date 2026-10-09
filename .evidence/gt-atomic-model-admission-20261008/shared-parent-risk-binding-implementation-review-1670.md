# 完整共享父风险原producer桥接复审（AOS-001670）

## 本波范围与验证
产品仅新增 `services/aos-api/aos_api/aip_physical_capacity_occupation.py::prepare_shared_parent_risk_plan`；旧函数定义未变。按已批准文件级计划，v3完整两case四leg经真实Source与原双父Owner核验后，同SCRAM、SERIALIZABLE、同xid/pid调用原private风险producer，并核验原完整申请、审批、父10/10、Source和case集合。最终Owner等待后再核Source期限。无提交、签名、实际占用、transport或权限扩大；正式库未动。

4非法caller拒绝；296纯累计通过且禁止PostgreSQL连接。R2 fresh实验原生节点1PASS83.12s，四负门与private读取/提前finalize/实际COMMIT拒绝，独立只读回读xid29687 aborted、风险/扣款/Intent各0、原Source1，冻结产品hash匹配。后端边界无浏览器适用项。完整Task仍ACTIVE、无Delivery。

## 必须保留的保护失败
R1业务节点1PASS84.12s，但运行器因pytest重复模块导入而保护补丁未生效，整次exit1。两个未跟踪旧实验摘要被覆盖：legal-model-prefix-application-r4.json、legal-eval-application-result-r4.json。before/after SHA与当前输出保存在R1诊断；精确副本、嵌套资料和本会话输出查找未找到事前原字节，未宣恢复。用户备份路径待答。

R2在pytest collection实际模块打补丁；备份仅为事故后基线，本次未再覆盖该基线。R2通过不能消除R1历史资料损失。本波不能声明全部保护验收通过；不使用这两个旧摘要的当前内容证明历史验收，也不将其纳入产品验收新提交。新实验资料独立保留。

## 剩余依赖及下一候选
1. 已登记typed/atomic合同：调查新v3完整manifest与原private风险行的持久hash、可信签名域、identity/Intent/joint provenance；当前bridge绑定原parents/cases/Source，但尚未把全部v3字段持久认证。安全独立，优先继续原件路径调查；迁移/新权限变动先完善方案。
2. 已登记atomic/shared-budget合同：实际token权威与真实占用、joint deadline/finalizer；token producer缺口及严格WAL/ACK截止用户裁决仍未完成。可调查原件，不能发明token或放宽deadline。
3. Prime只读恢复局部待用户授权；旧unknown attempt不重发。历史摘要恢复也是局部事项，不改变Goal。

不得以代码、测试或本桥接证据宣自然首链、正式安装或生产授权通过。
