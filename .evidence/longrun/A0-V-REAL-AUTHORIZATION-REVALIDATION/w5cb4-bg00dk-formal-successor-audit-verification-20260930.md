# W5CB4 BG00dk｜当前签名/安装/配置只读核验

- `scripts.a0v_current_preview_http.preflight` 对当前签名 receipt 退出 0：数据库 `aos_current_preview_20260927`，安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`，受检签名树为 `.aos-current-build-pyGkqQ/signing-state/signed-bundles`。只读 `psycopg` 立即设 `conn.read_only=True`，`alembic_version` 为 `a0v_118`。
- `docker --context colima-aos-extension volume inspect aos-a0v-recovery-pg-data` 退出 0，容器 `aos-a0v-recovery-pg` 运行；在 `colima-aos-a0v-test-only` 同名卷查询退出 1，证实必须显式选当前 context。
- 当前安装查询：`org-org/dev-project` 仅 1 行，approved@3、active_revision NULL、lock rev1；四包 resolved/published 一致，growth `1.11.0`、hash `sha256:3d8817e01f53690adbd58698951c226e8c3917304a9ec4d7eee37d64bf02b328`。`dev-org` 安装 0。
- 当前与新开发签名 receipt/key/trust-root 对账退出 0：当前 keyId `a0v-local-ecommerce-current-v1`、新 keyId `a0v-local-ecommerce-growth-1-12-v1`，根 revision 不同；新 growth hash `sha256:ca604f9b18dba305dfaa54bc6e47006e512fd6c810888fdeb41a223057be6bd1` 未在当前 Registry/lock。
- 当前全库 Host identity 0、精确租户 assignment/operation/binding/configuration 0；`read_candidates` 八项均 0。Host 预检仍 exit 2 `SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。`.env` 的 bundle root 匹配当前受检树，但 trust-root 文件路径不存在，且 signed receipt/credential/Host flag 未配置；当前受限启动器显式注入受检路径，不等同正式 Host 引用齐备。
- 历史 BG00ck 备份 `current.dump` SHA256 `8c609f6f…9cdce0`、`globals.sql` SHA256 `0a8c4dc5…23ecfa` 本波重算一致，均 0600，TOC 5615 行；它是 a0v_117 迁移前备份，新的当前迁移须再备 a0v_118。无删除/覆盖。
- 端口回读：8080 与 8434 仍监听，18181 不监听；端口存活只是旧进程可达，不代表最新 m1 代码已在当前 API/Web 重新载入。无 browser-pilot 截图。

本波没有代码或当前实例写入，RED/回归不适用。签名与安装边界及下一施工门见同名 plan；当前系统仍为 E16 安全禁入、E17 自然首链 pending。
