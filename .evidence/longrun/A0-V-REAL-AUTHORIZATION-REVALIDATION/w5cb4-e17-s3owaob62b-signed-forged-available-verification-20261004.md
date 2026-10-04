# b62b｜签名 Growth1.13 安装下普通 issuer 伪造 available RED

## 范围与方案复审

- 基于 231-3/BIND-1、b62 plan 与 b47–b50 隔离测试。仅两个 test-only 文件增加 `AOS_B62B_FORGED_AVAILABLE=1` 模式和普通 issuer 负门；生产服务、迁移、当前真库、浏览器页面均未修改。
- full-schema 夹具先验证 Growth1.13 本地签名树/信任根/发布、active Installation 与 b47 锁定 blocked evaluate。测试专用普通 issuer 获直接 Binding UPDATE/Receipt INSERT 后，尝试在同租户把 test-only Binding version2 改为 available、填自造 hash/有效期并插入 evaluate Receipt。期望 `InsufficientPrivilege`；实际无拒绝。它证明 signed 安装存在也不能让旧普通 issuer 的 evaluate DML 成为可信来源；不声称该 test-only Binding 已满足八依赖。
- 临时角色/policy 使用 `finally` 撤销并回读 `pg_roles` 为空；测试数据库名断言 `aos_test_*_ti4_test`。没有当前权威库写入。

## 本次验证

| 命令/模式 | 结果 |
| --- | --- |
| signed Growth1.13 full-schema，`AOS_B62B_FORGED_AVAILABLE=1` | exit0，`1 xfailed/7 warnings`。 |
| 同命令加 `--runxfail` | exit1，失败在 `plan_restricted_evaluate_case.py` 的 `pytest.raises(InsufficientPrivilege)`：`Failed: DID NOT RAISE InsufficientPrivilege`；证明 xfail 不是夹具预检、签名、OCI 或清理故障。 |
| signed Growth1.13 默认模式 | exit0，`1 passed/7 warnings`。 |
| signed Growth1.13 `AOS_B49_CONCURRENT_REVOKE=1` 与 `AOS_B50_EVALUATE_FIRST=1` | 分别 exit0，各 `1 passed/7 warnings`。 |
| `python3 -m py_compile` 两测试文件及 `git diff --check` | exit0。 |

## 结论与继续

- 本波是更强的隔离联合 RED，仍非可信 available GREEN。普通 issuer 直接 evaluate DML/Receipt 权限必须由唯一136受限命令收回；不可简单用页面禁用、可写 GUC、客户端 hash 或 Python 预检补救。
- 下一波需设计并证明同最终事务的可信八类依赖计算、签名 Installation/Registry 锁序、Binding CAS 与唯一 Receipt，兼顾 b49/b50 revoke 和安装换代；正式凭证/角色/ACL、当前卷新备份/全恢复/零执行窗口另门。Host/worker/Provider继续关闭，首链 pending。
