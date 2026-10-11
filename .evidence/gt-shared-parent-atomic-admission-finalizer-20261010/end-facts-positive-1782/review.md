# 本波失败收口与暂停交接

原完整 fixture 一次调用已终态：141.85 秒，call 在原 v2 Receipt 生成阶段因 CAPACITY_CURRENT_SOURCE_EXPIRED 拒绝，teardown 为 CAPACITY_NATIVE_SIGNED_SUPPLIER_INPUTS_REQUIRED。collector 正例尚未执行，不声称八节点读取正向通过或整个 Task 完成。

独立只读回读同 cluster/新独立库：九张原 admission 表全部 0 行，其他会话 0，产品精确 hash 不变。隔离新库保留，未重放，未放宽 Source/批准期限；正式库、Host/worker/Provider 未操作。原 SQL collector 留在独立试验库并保持原封闭权限，不能视作正式安装。

方案与证据一致：保留全部原合同、RED 与风险；上一波 50 PASS 仅元数据/专项累计。下一入口仍是原完整 Source 耗时/期限边界调查与完整 collector 正例、native ending/bootstrap/持久确认；本波收口后依用户准备重启指令暂停，不启动新一波。
