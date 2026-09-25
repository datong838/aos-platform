# W5c9d｜重启可复核的原组 Host no-authority 只读诊断

## 上位边界与目标

承接 W5c9c `m1@607fec6d`/AOS-000691，复习 W5c7t 控制面来源审计：仓库/本机没有覆盖所有机器、启动面、旧二进制/离线节点的权威 FleetUniverseRevision。旧 W5c5g 组合门依赖已经停用的独立 snapshot worker 10 秒新鲜状态，不能用在当前 snapshot=false 的纯 HTTP 18181。**本波只改善读数，不建立真实关闭权限。** 即使严格 24h 过线、已知本机 Host=0，仍 `topologyComplete=false`、`closureAuthorized=false`、`automaticAction=false`。

## 文件级清单

- 新增 `scripts/a0v_w5c9d_reboot_safe_host_diagnostic.py`：只组合现有 W5c4t 强制只读精确原组/时间分类、W5c5f REPEATABLE READ READ ONLY 受管目录分类，及本机 exact launcher PID 解析函数；不调用 W5c5b/c/g 的旧 `_worker()` 或真实 Owner。仅输出 outcome、原 Run/Receipt 聚合、knownLocalHostCount、timeGate、固定 no-authority flags，不打印进程 argv、DB/商城源行、DSN/凭据。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c9d_reboot_safe_host_diagnostic.py`：先 RED；覆盖未到线/到线、目录不完整、已知 Host 存活、未知/异常读数，所有路径三授权旗标 false；隔离单元测试不接真实 DB。
- 现有 W5c5g/W5c4q、真实 DB/Host/18181 配置不改。真实运行只读白名单结果，并对照 W5c9b 原十二 Run/零 closure Receipt；不把本机诊断当全机穷尽。

## 九步

1. 复习 231/231-9、W5c7t、W5c9b/c 与 no-effect 边界。
2. 本方案先提交。
3. 现行 PG/18181/租约/8080 与精确原组前检；测试 RED。
4. 最小新增只读诊断，不改任何 effect 路径。
5. 专项 GREEN、相关累计回归；真实只读诊断一次。
6. 方案/代码一致性复审：本机 0 不等于全机 0，时间门不等于授权。
7. 8080 业务浏览器离线；18181 `/docs` 不替代业务验收。
8. verification、m1、D-waves/AOS CAS/Prime。
9. 自动下一波：基于外部 Fleet/Owner 权威缺口继续研发可验证控制面接入合同或其他安全债，绝不直接关闭原组。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push、不读商城源。
