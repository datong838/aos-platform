# R23 完整隔离准备矩阵

Rules：231/joint §11.3，AOS-001689，m1单writer，现有Task10 E及同ownerTask3 E，真库只读。上一轮差异为四表未纳入签名准备子链，不能替代完整矩阵。候选①组合原cert/Source+Target call/ledger+Judge awaiting Intent；②实际Target结果→Judge执行producer（须合法后续合同）。先①，不降低第二项。

文件：本Task/native-r23/run-native-r23.py、source_newjudge_native_trial_1606.py、combined_prepare_trial.py、复制的新实验签名helper及结果/日志；Task3独立新label shared-native-combined-preparation-1689-r23。复制仅旧fixture只读源码，新运行新数据库/批准/Root/签名，不使用旧R22撤回原件。记录精确12冻结源hash、HEAD/TaskLease/authority/cluster/容量与claim；目标目录mkdir/O_EXCL，未知结果不重新运行。单实验，不改产品源码/原期限/原C ACL或全局角色配置。保留所有库与卷。

复用原R16成功准备helper，去除已登记caller-domain专项的重复执行；仍保留samecaller完整四证书/坏签名缺腿等5门及后写失败savepoint清理/幂等current identity验证。原Source/审批fresh既有独立窗口，Root仅实验bootstrap a*64，rootProvenanceVerified恒false，不延期旧证书。

新prefix沿原Judge Store已建后，在新实验admin安装原Judge Intent、prepared_call、Target call、Target ledger四表工件。所有原guard保持，无finalizer。新增仅test-only固定readback Owner helper，runtime只EXECUTE不DML，PUBLIC撤回，无正式接口。Risk samecaller在完整签名准备后走原创建Suite/Input→Target Intent→原planrisk→preparedTargetcall→ledger initial，再以原Judge申请创建awaiting_target_result Intent。仅第一实际case Target与Judge依赖准备（其余case仍whole manifest四leg签名）；不伪造Target result/Judge input/Usage，不预占超出Source全case并发。完整计划范围保留，待Target结果后才能下一call，不将此节点称全评测执行。

专项：同xid/pid原件、Target原inputHash/Suite/应用完全绑定、call/ledger原件哈希/幂等、Judge original targetIntent绑定/awaiting状态、runtime四表DML全拒绝、完整安装七guard/同名constraint组、actualCOMMIT拒绝，独立读取新库12风险/metadata行全部回滚0（Root单独预发布保留），原库无写。后续原基础Source相邻仍跑。出现RED保留结果/数据库先对账；无cleanupdrop库/未知重试/Provider。无UI故浏览器不适用。仍需实际结果/合法joint/WAL/Root正式谱系/经营首链，Task9/10不Delivery。

R23 terminalFAIL：仅复制runner/helper到新N，漏了原testModule通过EvidencePath要求的三合法fixture输入；不是产品缺陷或新增SQLRED。独立只读新库所有已有risk/metadata行0，combined安装未达，冻结12源hash全相等。R24新目录补三原fixture源码与精确新hash，再fresh新label/newDB；R23不重发不改，已终态，不复用其Source/approval。
