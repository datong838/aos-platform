# 电商 1.7 不可变候选验证

SDK 修复提交 e3f8daab；新三包候选 eefd0a8d，历史候选未改。首轮测试发现并纠正工作台 bundleRef 旧坐标，以及签名篡改检查硬编码旧 core 路径；后者现由 RUNTIME_CASES 派生。

构建器与 SDK 测试 29 passed，新 Registry successor 边界测试 7 passed（包含缺少 2048 心跳证明拒绝、根切换 CAS 与幂等）。真实 OCI 构建及每包 2048 心跳资格待执行。八模块数量不构成八业务场景完成证明。
