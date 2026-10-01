# 本次重启提醒验收失败记录

事件aos/2026-10-01T09:53:54.819Z。依提醒进行了新的现场预检，未因当天已有记录跳过。结果：SAFE_BLOCKED，未执行完整重启，未宣称验收通过。

- m1 HEAD 16604c73；旧browser插件/pnpm-lock dirty及历史untracked保留。只由本执行者写本次证据；未证明所有外部进程均无写入能力。
- colima：aos-extension、aos-a0v-test-only Running，default Stopped（exit0）。
- docker inspect：aos-a0v-recovery-pg running，权威卷aos-a0v-recovery-pg-data挂/var/lib/postgresql/data（exit0）。
- docker exec psql -U aos_app -d aos_current_preview_20260927 -X -At：BEGIN READ ONLY，数据库身份/版本aos_current_preview_20260927/aos_app/a0v_118，COMMIT，exit0。未查询商城源。
- 以API .venv Python读取Alembic唯一head：a0v_130，exit0。首次系统Python缺alembic，已换项目解释器，未安装或改环境。
- 最新脚本：services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json，exit2，单JSON reasonCode=PREVIEW_CODE_SCHEMA_DRIFT。此失败不证明完整安装/签名门已通过。
- 已存独立备份aos-recovery/.aos-current-backup-20261001-bg00gu/current.dump SHA256=e27b886f0a8fc94c6bc259b2a29250316d23f1e4d4567d3ea2589629d5d298f7，与GU恢复证据相符。本波只重新校验文件hash，未重新全恢复、未生成第二停机备份。
- launchctl print gui/<uid>/com.aos.a0v-api-daily0900 exit0：无OIDC配置键，未见--serve-limited；.env与apps/web/.env均无OIDC/Auth键。仅记录键存在性，不输出凭据。不能推断外部IdP不存在。
- 端口：18435 ssh8015、8080 python65249、8434 node59876，18181无监听；未停止这些进程。Web根页HTTP200。API所尝试/health、/healthz、/readyz、/api/health、/api/ready、/api/v1/health均404，健康状态未确认，不能用监听替代健康。

## 未完成与恢复入口

按455/456的当前切换门，需先明确独立受限API身份与正式OIDC配置，再零执行窗口、第二停机一致备份/恢复核验、当前118→130安全迁移，之后依序重启PG/API/Web并验证八工作台/权限/核心交互。仅GU旧克隆通过不能跳过此门；不启动旧owner模式冒充新版。
本波未修改库/卷、未迁移、未读商城源、未启Host/worker/Provider、未重放旧Run、未手工run_definition、未做浏览器业务验收。健康路径探测404如实记失败；不得声称已重启。
Goal状态本波不更改；原subject-review与首次Model评测用途裁决仍未收到。新提醒不是这些权限语义的批准。

## 18:01接续纠正（独立提醒aos-2/2026-10-01T10:01:24.874Z）

先读取当前HEAD4894a1bc、工作树、AOS-001070的01/06和前次Delivery；原API65249/Web59876进程仍存在，未重启或重复写业务。
源码services/aos-api/aos_api/routers/health.py第11/17行明确声明GET /v1/health与/v1/ready。此前猜测的六个路径404是探针路径错误，不足以说明API健康接口故障。
重新GET http://127.0.0.1:8080/v1/health → HTTP200 {"status":"ok"}；GET /v1/ready → HTTP200 {"status":"ready"}，curl exit0。两函数只返回静态字典，不访问数据库，所以这里只证明现存API进程响应，不证明数据库/签名/权限/业务准备就绪，更不证明本次已重启。原schema118/130禁入与正式启动身份缺口结论不变。
此次只读纠正，无服务启停、商城源读取、旧Run重放或Provider调用。下一次验收固定使用源码确认的路径；最新代码/数据卷/正式身份仍需独立核验，不再以猜测路径或200替代。
