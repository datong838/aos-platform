# BG00GU 当日备份与118→130隔离恢复演练 verification

基线m1 e8d699bf / AOS-001061；独立恢复准备波。生产代码未改，未切换当前实例。

## 当前现场

`colima list`：aos-extension/aos-a0v-test-only Running，default Stopped。`lsof`：18435/8080/8434监听，18181未监听。`docker inspect`只读核当前容器挂aos-a0v-recovery-pg-data。初次psql按通用postgres角色读取失败（该角色不存在），未执行SQL；回读既有BG00dl方案后使用实际aos_app只读查询成功，不改角色。

源：colima-aos-extension/aos-a0v-recovery-pg，aos_current_preview_20260927@a0v_118。只读SQL runtime_binding=0、host_assignment=0。原HTTP启动器签名预检命令：

```sh
services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json
```

exit0，CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN：approved安装ccdcb0f0-1040-4bc6-aa0c-d045f5689813、publishedVersions4、runtimeBindings0、version118。此预检保留原118声明，不是最新130实例验收。

## 一致备份和克隆实际操作

私有现场：`/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261001-bg00gu`，目录0700/文件0600。复用空闲独立恢复容器colima-aos-a0v-test-only/aos-bg00dl-isolated-pg的18440，未挂当前卷；新建唯一库aos_bg00gu_current_20261001，保留原恢复库及所有备份。

执行脚本`rehearse.py`先经py_compile，随后原样执行，exit0；SHA256 f30603ed5af25b8a969496f860a987608260ef33c94352ac67ee2cccb125c8a0。脚本固定source/clone/卷/port/m1/head/版本、目标已存在即拒绝，步骤intent/done均独立保留，禁止重跑覆盖。凭据仅进程内读取原受控配置，无命令参数/日志/提交明文。

| 操作 | 实测证据 |
|---|---|
| 一致备份 | source REPEATABLE READ READ ONLY + pg_export_snapshot，pg_dump -U aos_app -d aos_current_preview_20260927 -Fc --snapshot；exit0 |
| 备份完整性 | current.dump 3,961,457 bytes，SHA256 e27b886f0a8fc94c6bc259b2a29250316d23f1e4d4567d3ea2589629d5d298f7；TOC5621行 |
| globals保留 | --globals-only --no-role-passwords，exit0，SHA256 8a090afb310b941a460f5b7783783c71a084766377e32307c5a33658818f2909；未覆盖隔离旧角色 |
| 全库恢复 | 新库template0/owner aos_app/revoke PUBLIC CONNECT，pg_restore --exit-on-error；exit0，source/clone均118；580张原public表行数全部相等，17个固定控制表行hash、两类原元数据逐ID行hash完全相等 |
| 最新迁移 | 原Alembic程序化连接限定clone，用原aos_app表owner执行DDL；119…130逐步事务/版本回读，12步全部exit0；未stamp、未关闭保护、未启LOGIN |
| 升级对账 | clone130，新增7表；两类策略元数据各按迁移新增3项，其原行hash不变；其余580原表计数保持，除版本表外固定控制面hash保持 |
| 源复核 | 结束后新READ ONLY事务重读源，version118，580表计数/17控制摘要/旧元数据摘要与备份快照一致；sourceWrites0、ProviderCalls0 |

独立补充查询正确角色名称（初始脚本漏列实际aos_budget_consumer_call/owner，未把缺失行当存在证明）：共9个指定签发/消费角色均NOLOGIN/NOSUPERUSER/NOBYPASSRLS；3个消费函数对aos_runtime无EXECUTE；8个Guard/Quota/Budget/Network写保护触发器均enabled=O。补充断言exit0。

- backup.json SHA256 846b316cd8b2a65909a3ba15ce9a432a59072c585ca7cea88d2091a26cb63824
- verified.json SHA256 33ba22065fd5a2a23c32b2c2ff8a2878d4ad4c239099cabb81e32eb2492873d3
- activation-boundaries.json SHA256 5ecc175edbafd6f0d2e914d12e65bba5ece309d8ef2dd871212081639d5f18d8
- 日志/tmp/aos-gu-clone.log；阶段结果FRESH_RESTORE_AND_118_TO_130_CLONE_GREEN。

## 复审与未完成

这次证明真实当前库备份可恢复、12步代码迁移可在独立克隆运行、控制面与禁入默认保持；不是自然首链或正式消费者跨身份运行验收。没有产品代码变更，不新增无关单元回归，浏览器不适用于此纯恢复操作。

当前实例仍118、未重启，今日最新版本重启验收仍未完成。下一独立波BG00GV：复习当前受限API启动身份/代码版本门、计划与RED更新启动器预期130；核可恢复备份/克隆后建立零执行窗口和第二份停机备份，再决定当前迁移及PG/API/Web完整重启与八工作台/安装/租户只读浏览器验收。未具备前置门不得切换或伪称最新。

BG00GT模型评测用途授权仍等待用户裁决，未编码；watchdog仅方案未部署。当前无商城源读取、旧12Run重放、手工run_definition或230L0动作，Host/worker/Provider未启，Goal active，不push。
