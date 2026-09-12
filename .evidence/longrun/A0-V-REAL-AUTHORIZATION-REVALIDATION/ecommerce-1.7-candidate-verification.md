# 电商 1.7 不可变候选验证

SDK 修复提交 e3f8daab；新三包候选 eefd0a8d，历史候选未改。首轮测试发现并纠正工作台 bundleRef 旧坐标，以及签名篡改检查硬编码旧 core 路径；后者现由 RUNTIME_CASES 派生。

构建器与 SDK 测试 29 passed，新 Registry successor 边界测试 7 passed（包含缺少 2048 心跳证明拒绝、根切换 CAS 与幂等）。真实 OCI 构建及每包 2048 心跳资格待执行。八模块数量不构成八业务场景完成证明。


真实构建基线 7ec6f4e0、输出树 sha256:0a29ad14933c4155bc06de7fd5bd95519d7a893b119513ce66da544c006a4dae。三镜像各 2048 心跳、注册 1/2/23、cleanup released，七篡改拒绝。Registry 各新坐标 create/validate/publish 一次，重放全部零，v6 历史八坐标保留。Schema 各 13 关系核验且无新增迁移登记。旧 efc 安装 uninstalled@6，同键重放 true，新安装已正式 approved。重装/Schema 单测 11 passed，7 项显式 PG 测试因环境门跳过；不计为通过。真实卸载结果另有本库 Receipt。

下一波新 Host apply/verify 及长期观察，尚不能标连续运行完成。
