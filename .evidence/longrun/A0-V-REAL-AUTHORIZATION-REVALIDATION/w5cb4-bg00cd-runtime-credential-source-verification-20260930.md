# W5CB4 BG00cd｜运行身份明文来源移除验证

## 基线与消费者盘点

AOS-000932、m1 `14690b20`，当前权威 PG `aos_current_preview_20260927@a0v_117`、Host/worker/Provider 关闭。已确认当前 8080 `a0v_current_preview_http.py` 使用恢复容器的 `aos_app` 启动，非此 runtime 登录；当前 PG `pg_stat_activity` 对既有 runtime/web/directory 三登录活跃会话为0。既有 mode600 三身份文件中 runtime 密码与历史 `scripts/a0v_w6_bg03_candidate_scan.py:36` 字面量匹配。`git ls-files` 14607 个文件中原仅该路径含字面量；旧 `a0v_bm_runtime_credential_rotation.py` 指向 `aos_meta_head`，文件存在时只对账，不可用于本次轮换。全程未输出密码、未读取历史商品库或商城源。

## RED、最小实现、验证

先新增 `services/aos-api/tests/aip/test_w6_bg03_candidate_scan_credentials.py`：缺文件、权限0644、角色/host/port/db 漂移失败，私有假凭据可读取，源文件不得含密码字面量。RED 6 failed，原因 `_runtime_dsn` 不存在；pytest 全局 fixture 在独立 `aos_test_*_ti4_test` 临时库执行迁移并按其清理规则删除，当前真实库回读仍 `a0v_117`。后续显式 `AOS_TEST_USE_SHARED_DATABASE=1` 仅用于跳过全局建库 fixture，本组纯单测不连业务库。

只修改历史脚本的 DSN 来源：惰性使用既有 `_load_credentials()` 校验 mode600 三身份文件，解析 runtime DSN 并严格检查固定 login/host/port/旧库名。候选选择、租户、输出与原 SQL 不变；脚本本身未执行。专项6 passed；相邻累计 33 passed/2 skipped；`compileall`、`git diff --check` 退出0。读取当前受限凭据后只在内存扫描 14607 个跟踪工作树文件，匹配路径0；当前 DB 只读回读仍 `a0v_117`。未触碰用户另有的 browser 插件/pnpm 锁变更和两个 test-only 现场文件。

## 方案一致性与剩余风险

本波只移除当前源文件的明文，不把历史脚本当正式业务验收；它保留原 `aos_meta_head` 指向，不被执行，符合不读商城源。当前密码仍有效、Git 历史仍含旧值，安全风险 OPEN。PG 角色密码是 cluster 全局状态，单一当前库 dump 不能恢复角色密码；下一波 BG00ce 必须含 cluster globals 可恢复备份及独立 PG 集群旋转/回滚演练，不可对当前共享 cluster 的 test-only DB 直接 ALTER ROLE 作为隔离测试。盘点潜在离线消费者后，在零执行窗口轮换既有 runtime 身份、原子更新 mode600 文件、旧密码负例/新密码正例与三平面预检；不改变当前 API 超级用户登录或擅启 Host。网络 Event 发行角色与 API 登录收紧按后续波次继续。
