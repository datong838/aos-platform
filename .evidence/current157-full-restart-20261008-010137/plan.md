# 本次提醒：原卷最新已提交版本完整重启

event 2026-10-08T01:01:37.490Z，m1 HEAD 8658a3fcb75d280eb454bc342629af8a9fb72c80，authority001518。独立维护Task/三个资源Lease由原唯一Owner登记，其他14Lease不变；首次登记因漏paths参数TypeError在函数调用前失败，核没有Receipt后更正，非未知效果重发。

从git archive精确HEAD冻结 services/aos-api、scripts、bundles、apps/web、packages；不导入未收口工作树158/Model/occupation。冻结API路径的Alembic head和当前库均157，不迁移、不以工作树158当当前代码发布头。Web使用同HEAD源和现有已安装依赖，只在新冻结根创建node_modules链接，不改已有源码/依赖/锁文件。逐文件Git blob核验，无archive覆盖现有根。

先签名Receipt预检（既有批准安装/157/0runtimeBindings）与当前只读完整用户表hash、public目录、库卷/镜像/容器身份核查；此门失败不停止服务。每次实际操作前核HEAD、Authority、Task/Lease、源码/既有进程argv/cwd/UID/start和唯一端口，O_EXCL/fsync写intent。精确SIGTERM旧API3876/Web99310（原helper99311），确认端口退出和helper退出；不kill未知PID、不强杀。docker在colima-aos-extension仅重启原容器9cc6091c…，卷aos-a0v-recovery-pg-data、端口18435和库aos_current_preview_20260927保持。PG ready/启动时间改变后，依次启动冻结最新API→Web，核新PID/start/argv/cwd/端口，health/ready/库157/签名安装与禁入标志。

前后SERIALIZABLE READ ONLY比较全部用户schema所有表行count/hash和public catalog（不仅旧602），不读取或打印凭证/业务原文。八工作台浏览器真实读取及只读目录重试，org-org/dev-project正向；dev-org仅403无效果canary，安装目录只读，浏览器保留。Host/worker/Provider保持off，当前预览栈重启与自然首链分报。

只运行本次claim一次；未知失败先只读对账，禁止重放操作。数据hash/签名/进程身份漂移先诊断，不改私有Goal/不删除库卷备份、不push。完成后本维护Task精确证据Delivery，随即回本Model已登记主线；没有新产品代码，无新单测冒充首链。脚本只写本证据目录与精确登记新冻结根，不改旧脚本硬编码版本门。

Web r1 已知失败：PID27005退出、8434无listener；配置 import vitest，但依赖在原 apps/web/node_modules，不在根依赖目录。最小修复仅在新冻结 apps/web 下增加原已安装 node_modules 链接，记录目标与包入口hash，不安装依赖、不改产品config/源码/锁文件。已完成PG与API不重启，先独立核当前PG启动身份/API26897/健康，再单独O_EXCL web-repair-r2启动与验收。失败r1原文件不覆盖，全量前后数据比较保持同一before快照。
