# W5c8t｜8080 零执行隔离前置检查器与受控停用计划

## 上位/事实

承接 W5c8s `m1@67620397`/AOS-000681：当前 8080 launchd `RunAtLoad/KeepAlive`，Host=1、snapshot worker=true independent、Cron/迁移未显式关闭；真实 profile 停止、容器 restart policy 未知。不得先启真库再检查。启动 plist 内含明文 DB 口令，检查器只能按允许名单输出布尔/状态，不能打印 plist、进程环境或 DSN。

## 文件级清单

- 新增 `scripts/a0v_real_profile_preflight.py`：**只读**解析指定 plist 和当前 `launchctl`/端口/Colima 状态；输出不含路径、凭据或任意原始环境值的 JSON：8080 是否仍被 launchd 保活/监听、四项零执行旗标（Cron=false、snapshot=false、Host=0、migration=disabled）、18181 监听数、真实 profile 状态与 container-policy-proof（默认 unknown）。只有所有证明成立且真实 profile 仍 stopped 才允许后继单独审批 DB-only start；检查器本身绝不启动/停止进程。
- 新增 `services/aos-api/tests/test_a0v_real_profile_preflight.py`：RED→GREEN，含恶意/含 secret plist 不泄露、缺旗标 fail-closed、KeepAlive 活动 STOP、伪造读回/命令异常 STOP、状态摘要稳定；不得读取真实凭据。用测试临时 plist/命令结果，不接真实端口。
- 本波是否停用真实 8080 另做只读依赖审计：若不能证明 `bootout` 不被其他服务自动恢复或安全回滚，暂不动服务。真实 profile/container restart policy 未知时继续 STOP。凭据轮换列后续受控安全波，不在本波输出原值。

## 九步

1. 复习 AT/W5c8s 与 launchd/脚本、m1/产品边界。
2. 方案落盘提交。
3. 先 RED 检查器缺失和缺旗标/敏感输出负例。
4. 最小只读实现，无真实服务状态变更。
5. 专项/累计、静态、真实 profile 停止回读。
6. 无 UI 时仅只读可达性；不冒称真实浏览器验收。
7. 方案/代码一致性、安全输出/TOCTOU 风险复审。
8. verification、m1/D-waves/AOS CAS/Prime。
9. 自动 W5c8u：依据检查器 STOP 原因，设计 8080 launchd 受控 quiesce 与 VM 内容器策略证明；未证前仍不启真实 profile。

230 L0 挂起、商城源不读、dev-org 零 canary、unknown 不重发/不手工 `run_definition`、不 push。
