# 第二次休眠后精确禁用当前实例

2026-09-12，基线 e7b1994c，m1 单人。目标仅现有 sleep-recovered state 指向的 a0fd8e25-cb6f-49e5-aa77-7faddae12099；旧 generation 49427eeb-e9f8-42d5-8588-108e90110beb 已释放，binding unknown/desired enabled/实际 false/fenced@5。Host v13 已启动。先正常 disable 使期望状态也禁用，不直接改状态或重建旧租约。

文件 scripts/a0v_ecommerce_1_7_disable.py 添加与 after-config-recovery 互斥的 after-sleep-recovery 参数，复用 configuration_target 的 UUID/旧实例排除及独立文件/幂等前缀；disable_target/run 新 keyword-only sleep_recovery，不改既有两个入口。测试 services/aos-api/tests/extension_runtime/test_a0v_recovered_configuration_target.py 证明旧目标不变、新命名空间不冲突、双目标拒绝。

执行顺序：只读核对当前 installation/generation/binding、无未决 operation；冻结命令后仅调用既有 RuntimeDisableService，沿实际 actor Membership 和 CurrentControlPermission，正常 Host 消费。unknown 不换键或手写成功记录，只读查询原 operation/event。成功标准为 succeeded、disabled_committed、期望/实际均禁用且资源确认释放；不以 accepted 为成功。无源读取、Provider 或外部发布；230 L0 挂起、不 push。

下一波正式检查未调度、未决调用和安装卸载约束，准备新 Niushop 1.4 的不可变发布组合及新安装。不能用静态/资格标签替代已签名版本和当前审批，不覆盖同坐标旧内容。

执行前验证：新增目标选择 RED 1 failed/11 passed，修改后目标/禁用执行器/两个真实隔离 PG 文件合计 34 passed，无 skipped。12:53Z 真实只读预检：四个历史 operation 均终态，旧 runtime-apply failed@386，verify/configure/enable succeeded；三资源 released 且 observed_release=true，统一期限11:58:22Z。binding仍unknown/desired enabled/实际false/fence true@5。ecommerce-second-sleep-disable-preflight.json保存完整非业务数据证据。一次测试误指定不存在文件未执行任何测试，已更正为实际文件；首次只读预检误把资源表当作有installation_id，整笔只读事务失败，改用scope+operation关联查询后成功，未写数据库。
