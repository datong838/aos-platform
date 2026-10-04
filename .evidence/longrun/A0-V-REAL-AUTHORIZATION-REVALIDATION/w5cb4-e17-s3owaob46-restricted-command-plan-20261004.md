# E17 s3o-w-ao-b46：受限 evaluate 命令原子边界

## 上位合同与已有证据

231-3/BIND-1 要求当前安装、依赖、Binding 与 Receipt 不漂移；b41 已在隔离签名安装证明无表 UPDATE 的安装锁函数，b44 证明发行账号即使私有，持 Binding UPDATE 仍可伪造合法外形 evaluate，b45 仅提供同事务 Readiness Reader。当前正式 issuer/Reader、active Growth1.13、八配置/六 Binding 均缺，权威库135只读；代码迁移头不得单独升到136。

## 文件级范围与顺序

1. 新增 `services/aos-api/tests/aip/test_e17_s3owaob46_restricted_evaluate_command_pg.py`。使用 disposable full-schema PG 随机创建 NOINHERIT/NOBYPASSRLS 测试调用者与 NOLOGIN/NOBYPASSRLS 函数 owner；所有角色/函数测试后精确清理。先 RED：调用者对 Binding UPDATE、Receipt INSERT 无表权，函数不存在/未授 EXECUTE 均拒绝。只在克隆授专用函数 EXECUTE。
2. 测试函数只允许 `blocked` 且原因 `TRUSTED_EVALUATOR_PENDING`，不接受客户端任意 readiness/hash/有效期，不创建 active/runnable 权限；函数 owner 在同一事务做 exact tenant GUC/session_user/Binding version CAS、更新与唯一 Receipt，失败回滚。错租户、错版、同 key 不同请求、双提交和普通 runtime 调用负例。此为最终命令的原子失败关闭切片，**不**代表完成完整 evaluate 或安全激活。
3. `aos_api/aip_capability_binding_service.py`、迁移与当前库本波不改；在下一波把 b37/b41 当前签名来源锁、b45 同事务依赖计算与此受限命令合并，验证撤销/替换并发和 available 正向前不得解除 b34/b37/b44 xfail。任何正式 DB 迁移需唯一136合同、新一致备份、全恢复、零执行窗口。

## 验收与边界

专项及相邻回归、权限与事务回滚读回、函数/角色 cleanup0，结果仅为隔离命令基础 GREEN；当前实例仍禁入，Host/worker/Provider关。租户正向只用 org-org/dev-project，dev-org 仅负例；不读商城源、不重放旧12Run、不手工 Run、不碰230 L0、不 push。
