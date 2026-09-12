# Niushop 1.5 独立构建与资格方案

2026-09-13，基线 e6761c1d；Lease A0V-NIUSHOP-PRODUCT-BUILD-20260913。

新增 scripts/build_niushop_product_candidates.py；测试新增 services/aos-api/tests/extension_runtime/test_niushop_product_build_profile.py。复用既有 builder，以私有 module 将唯一 Niushop 1.3 坐标替换为 1.5；不改变原 builder 默认或 1.4 profile。守卫旧坐标唯一和 ALL_CASES 前缀完整；原 core1.3/growth1.7/operations1.2保持。

先测试 RED，再实现；检查实际 manifest、注册贡献及原 profile 独立性。提交固定源后，输出到仓外 .aos-recovery-20260913/state/niushop-1.5-build-v1，日志同 recovery/logs；使用 colima-aos-extension，按原工具隔离容器与临时签名做资格验证。真实 OCI registration/2048 heartbeat/cleanup、篡改拒绝及四坐标 resolution 均须通过。构建不能替代 source schema 或安装验收。

本波不修改 Registry、签名运行目录、当前安装实例、数据库和 API/Host 配置。失败保留 receipt，未知容器结果先观察不盲重试；构建输出路径已存在则不覆盖。下一波另行制定 append-only Registry successor 与 current installation 升级方案，先验证 schema 和当前实例引用。

实现核验：新 profile 缺失先红 1 failed；实现后新 profile 与原 builder 联合 12 passed，4.56 秒。实际候选声明匹配，原 1.3/1.4 profile 独立不变。接下来先固定提交再构建，构建及资格尚未完成。
