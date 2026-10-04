# b54 文件级方案｜正式卸载角色 ACL 隔离反证

## 上位/已读事实

- 231-3 要求运行卸载经正式停用、排空、资源释放和原子 Receipt；`ar2_018` 刻意只给 `aos_app` EXECUTE，原隔离测试已有 app 正向、runtime 负向。b53 当前库只读证实 aos_runtime=false、aos_app=true、无继承。生产 `PostgresInstallationStore` 使用 `db.connect`，`apply_asset_transaction_scope` 在当前 TI6 schema 切到 aos_runtime，因此组合入口与函数角色合同不一致。
- 不能简单向 aos_runtime 授函数 EXECUTE：原测试 `test_runtime_role_cannot_call_application_uninstall_command` 明确防止运行 worker 自行终结安装；此权限必须保持负门。当前 API 预览使用特权 PG 预检身份，不算正式低权生产者。

## 本波动作

1. 优先复跑既有 PG `test_runtime_uninstall_guard_commits_exact_terminal_authority`、`test_runtime_role_cannot_call_application_uninstall_command` 与同事务约束；原18434 test-only listener 缺失时在 `colima-aos-a0v-test-only` 建无卷的可销毁 PG 容器，绝不触碰当前权威卷。
2. 对照现有工厂/连接代码提出两身份同事务的最小设计：应用安装命令必须以 app-role 登录/事务完成；runtime worker 保持不能调用终结函数；不能靠 HTTP roles、owner、`SET ROLE` 到不受控高权角色代替正式登录。
3. 本波先定权限/接线 RED 与迁移依赖，不新增136、不当前库 GRANT。若已有测试足以给出精确反证，则只登记审计 checkpoint，下一独立代码波选最小入口和凭据来源。

## 完成判据

隔离 app 正向与 runtime 负向、同事务 Receipt 反证均可复核；真实库只读、Host/worker/Provider关，首链不宣称通过。
