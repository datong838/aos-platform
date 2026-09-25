# W5c8l｜空 canonical 见证 sidecar 基础验证

## 判定

本波**隔离 PG 结构/权限 GREEN，真实回填与 ACK 未实现**。方案 `m1@01179992` 先行；真实 profile 停止、真实数据库未迁、8080 未重启。无商城源读取、无 unknown attempt 重发、无 Worker 接线。

## 第 1/9—9/9 步

1. 复习 W5c8j/k、`a0v_045/096`、原历史表不可变/RLS、m1/AOS-000673、测试环境。
2. 先提交文件级方案 `01179992`，排除原表 UPDATE 回填、限定空 sidecar。
3. 隔离 PG 测试先 RED：`to_regclass` 为 NULL；迁移后测试最初因 `regclass` 显示省略 `public.` 的断言形式失败，改为检查存在而未改生产行为。
4. `a0v_097` 新建空 sidecar：双键/组、原 claim hash FK 与原 input 组 FK、文本大小/JSON object/sha256 检查、FORCE RLS、不可变三操作触发器；无运行角色写授权、无数据回填、downgrade fail-closed。
5. 空表/权限专项 `1 passed, 7 warnings in 4.46s`；原保存组夹具写入、UPDATE/DELETE/TRUNCATE 拒绝及假组身份拒绝 `1 passed, 7 warnings in 120.36s`；相关短累计 `31 passed, 2 deselected, 7 warnings in 11.21s`。`py_compile`、`git diff --check` 通过，`aos_test_*` 库 0。
6. 无 UI 功能改动；8080 health 可读但真实目录此前不可用、IAB localhost 上波被客户端阻断，本波没有业务页浏览器验收，**不判真实 GREEN**。
7. 方案/代码审计详见同目录 audit：manifest hash 尚未对原 input 精确 FK，数据库 owner 仍可插入；当前结构与测试不能授权 backfill 或 ACK。真实库未迁入 a0v_096/097、真实旧入口撤权未生效可证。
8. verification 与迁移/测试同 m1 提交；再更新 D-waves、AOS CAS、Prime 回读。`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false` 不变。
9. 自动进入 W5c8m：先只读历史逐行扫描与拒绝矩阵（隔离 PG 优先），再另立受控 backfill writer；无全链授权不建 ACK SQL、不动真实库。

230 L0 挂起，dev-org 仅零 canary；m1 单写不 push、不动其他分支。
