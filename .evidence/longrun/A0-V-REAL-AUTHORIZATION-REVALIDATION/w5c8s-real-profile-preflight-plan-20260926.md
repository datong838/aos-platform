# W5c8s｜真实 profile 重启前只读门与迁移顺序方案

## 上位/现场

承接 W5c8r `m1@eb2c56b7`/AOS-000680。真实 A0-V profile `aos-extension` 停止，真实 DB 状态不可读；此前原 12 Run/Receipt 为旧快照，不能当现时事实。AT/AS 事故证明 HTTP 与自然 worker 不可混启，旧 unknown 不得重发。`a0v_096/097/098` 仅已提交代码/隔离 PG 测试，真库未迁。此波先在**不启动真实 profile**条件下形成启动风险清单和只读恢复顺序；有自动重启容器/worker 未知项即 STOP。

## 文件级清单

- 复习 AT 保存快照恢复计划、W5c8h–r verification、Colima profile 配置、真实 DB 容器/launchd/8080/18181 启动脚本和迁移开关；只读 `git`/本机进程/配置，不读商城源、不访问真实租户业务数据。
- 新增本波 audit/verification 到 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`：列出真实 profile 的容器 restart policy、可能的自动 Cron/snapshot worker/Runtime Host、8080 指向、迁移 on-start 风险；每项区分已证/未知/停线。
- 对 `a0v_096/097/098` 做离线 migration DAG/权限 diff 审核；不得靠隔离 PG GREEN 直接 apply 真库。只有事先证实 DB-only 且 worker/Cron/第二 Host 全关，才可另波考虑重启真实 profile **纯读回**；本波不执行 profile start、真库迁移或侧表回填。
- 遗留“合法提交但恶意自洽”历史输入夹具列为后继隔离 PG 工作，不用真库造负例。

## 九步与停止

1. 复习上位与现场 HEAD/冻结门。
2. 本方案先提交。
3. 只读盘点真实 profile/进程/开关/迁移 DAG。
4. 无代码；如需新 guard，另修订方案再编码。
5. 配置证据交叉核验、静态检查；无本波代码测试时标 N/A。
6. 浏览器仅只读可达性，业务页不可验收不填 GREEN。
7. 方案与风险复审，任何未知自启动即 STOP。
8. verification/m1/D-waves/AOS CAS/Prime。
9. 自动 W5c8t：依据审计结果，若启动门齐全再形成 DB-only 受控重启/只读读回执行计划；若不齐先补启动 guard/隔离测试，仍不触碰真库。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
