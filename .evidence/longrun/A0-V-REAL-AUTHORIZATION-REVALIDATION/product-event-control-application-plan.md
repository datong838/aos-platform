# BG-02 领域包控制命令与回执

基线73f3c89f。产品目标是用户明确启停已保存的事件策略；保存不等于启用，回放旧回执不代表当前仍启用。包只构造业务意图，Host独立核实当前批准、角色、来源和安装。

新增backend/ecommerce_growth/ecommerce_product_event_control.py：固定六字段控制命令，从重验policy和DispatchRef取得租户一致性；严格引用、原幂等键、CAS版本及启停意图。无平台导入。校验回执固定信封、正文hash、原命令、租户/策略/版本/启停结果，校验确定性receipt UUID。结果不明只抛错不重试；原回执不转为当前状态。

修改ecommerce_business_investigation_application.py：末尾可选control_port参数，独立control_event_policy方法调用一次端口；不改变旧write/runtime/review逻辑。新测试test_product_event_control_application.py覆盖Host合同互通、启停、原key恢复、超时单次、伪造hash/跨租户/布尔版本/缺口端口拒绝。回归旧应用、控制Host及AR2闭合。代码改动目录仅上述包文件及services/aos-api/tests/extension_runtime；不部署。
