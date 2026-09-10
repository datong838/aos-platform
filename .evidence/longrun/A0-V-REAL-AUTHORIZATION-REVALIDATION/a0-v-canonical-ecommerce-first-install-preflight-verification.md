# A0-V Canonical 电商首装 Preflight 验证

## 1. 结果

`A0V_CANONICAL_ECOMMERCE_FIRST_INSTALL_PREFLIGHT_GREEN`。

新增首装执行器的默认模式已对 v4 build/qualification receipt、外部 staging tree、源码祖先关系、受控路径无漂移、四包精确版本、三个 runtime admission、三个 schema requirement 和七类篡改矩阵完成绑定校验。默认模式没有连接数据库、调用 Docker、创建签名密钥或写入 Registry/Installation。

## 2. 改动路径

- `scripts/a0v_canonical_ecommerce_first_install.py`
- `services/aos-api/tests/extension_runtime/test_a0v_canonical_ecommerce_first_install.py`

显式 `--apply` 还要求 `--database-name aos_meta_head`；其他名称在任何数据库连接前以 `EXPLICIT_ISOLATED_DATABASE_REQUIRED` 失败关闭。apply 的后续阶段仍由执行器显式阻断，不能越过尚未实现的备份、签名和生命周期步骤。

## 3. 验证

- 首装/构建器专项：`9 passed`。
- 真实 v4 preflight：`PREFLIGHT_GREEN`。
- build receipt：`sha256:b473385f353d28dfe5cd6a04cf4c8610c7b77496c7558e4f429271fa8a510638`。
- qualification receipt：`sha256:e8574f6b3bf2d7eb4d22bf811dc06174ffce18fe8f7f091a0bbebfd93f592da0`。
- staging tree：`sha256:26a5942e8087252df8f72e5430e4c4c6e42c906a8f814fe2df428d33c1293950`。
- 四类效果计数均为 0。

七条既有 Pydantic/Starlette warning 和测试进程退出时的 JDBC 日志关闭告警不影响结论。

## 4. 下一步

继续在同一执行器内接入隔离库身份/基线只读预检、apply 前逻辑备份、仓库外持久签名根、canonical Registry 与无 baseline Composition/Installation。任一阶段发生 unknown outcome 时只回读对账，不自动重发。
