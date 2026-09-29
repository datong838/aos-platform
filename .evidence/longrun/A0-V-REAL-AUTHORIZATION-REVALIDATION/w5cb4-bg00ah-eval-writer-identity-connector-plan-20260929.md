# W5CB4 BG-00ah｜默认关闭的 Eval writer 独立身份连接器方案

## 上位与当前状态

BG-00ag 当前库只读证明 `aos_app` 是 SUPERUSER/BYPASSRLS，普通 runtime 四张 Eval authority 表仅 SELECT，无独立 Eval writer。参考 `aip_capability_publisher_connection.py` 的受保护文件/独立 LOGIN/精确角色可达性模式，新增**专属 Eval writer 身份连接器**，只负责证明登录身份，不授表权、不创建正式角色/账号、不写当前库。正式 issuer/Owner/批准缺失时未配置即返回 None，生产 Skill guard 继续。

## 文件和测试

1. 新增 `services/aos-api/aos_api/aip_eval_writer_connection.py`：固定环境引用 `AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE`，文件须绝对路径、regular、owner=进程 UID、0600、NOFOLLOW、大小受限；严格 JSON 唯一键 `{schemaVersion,dsn,role}`，schema `aos.aip.eval-writer-identity/v1`，目标 NOLOGIN role 固定 `aos_aip_eval_writer`，DSN 不打印。连接后在独立短事务确认 `session_user=current_user` 是独立非超级、非 BYPASSRLS/CREATEROLE/CREATEDB/REPLICATION 的 LOGIN/NOINHERIT；只能到达唯一目标 NOLOGIN role，不能 ADMIN/继承普通 runtime、aos_app 或别的角色。失败关闭，不回退 `aos_runtime`/`aos_app`。
2. 新增 `services/aos-api/tests/aip/test_aip_eval_writer_connection.py`：缺配置、坏文件/重复键/错 schema/错角色、用当前 superuser 或非专用 login 均拒；test-only PG 创建仅用于机制的独立 LOGIN/NOINHERIT 与固定 NOLOGIN 角色，0600 文件连接正向，再授额外角色证明拒绝。账号/凭据仅在 test-only context，绝不迁到当前库；不授 Eval 表权。
3. 先 RED 再最小实现、专项/相邻回归；verification/上下文/D-waves/m1 精确提交。正向连接仅证明身份形状，不证明正式 Owner/issuer、授权写入、S3、Report/Gate 或首链。
