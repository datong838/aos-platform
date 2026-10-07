# 本次维护方案

事件：2026-10-07T17:15:17.220Z；唯一线程 01a107a2-e9e4-7670-bc44-1144fa9b27e2。

先独立只读核对 m1 HEAD、全部重叠 Lease、权威库/原命名卷/迁移头、原签名服务来源及进程。保留既有工作树改动，冻结已提交迁移文件，不把未交付 Source/Profile 工作树带入签名构建。

当前库151领先关系须现场确认；最新代码157。先冻结完整零执行窗口、停止精确原 API/Web、PG TCP 禁入并排空，第二份一致备份和 globals（私有目录），独立新卷完整恢复验证全部数据/目录/角色。逐步152至157原Alembic在线事务演练（157原生目录审计不能由旧离线执行器替代），检查旧数据不变、新增对象权限/目录，所有步骤 terminal 0后才精确迁移当前库。每一步先 intent 后单次执行后 terminal/done；未知结果只读对账，不重发。旧151执行器不放宽固定历史门。

然后恢复原配置来源并重启同卷 PG、当前 HEAD 独立签名安装来源的 API、Web，核启动时间/端口/健康/版本/库卷/禁入/租户。保留浏览器逐项核八工作台及只读交互；负门不当正向业务。原库、全部备份、恢复卷留存；Host/worker/Provider保持关闭。

本目录只写维护计划与证据；如需新执行器先追加精确 scripts/tests 文件计划、独立 Lease、RED/最小改动/专项与相邻，未授权源码不能混入。当前阶段仅只读预检，不执行迁移或重启。

## 首份一致备份与独立恢复文件计划
新增本目录 `capture_restore151.py`：固定源身份、m1 HEAD/Task/Lease、只读导出快照；仅允许源 pg_dump/pg_dumpall/pg_restore --list。私有新目录 `../aos-recovery/current157-<随机阶段>` 保存备份；新 none-network 容器和独立新卷恢复，限制 pg_restore 内存，全部保留。此步使用已有经测试的完整151快照和已审CHECK结合律比较门，记录实际差异列表；源快照前后精确相同。未写当前库/停止服务，不能替代后续零执行窗口第二备份。

## 原 Alembic 在线逐步演练
157 的升级入口需要原生连接和目录审计，不能假装能沿用151离线SQL执行器。先从精确 m1 HEAD 提取独立只读代码快照，不导入当前未提交模块。另建本Task独立 internal 网络、新容器/新卷，以首份完整备份恢复，并经独立 SSH 本机转发连接，仅用于原 Alembic 在线六步演练；不连接当前库执行DDL。对每步保存源码hash、前版本、intent、terminal、后版本、全部603旧表数据hash（除迁移版本），SQL日志/目录及私有安装审计。网络不允许外网，SSH私钥只由现有客户端使用，不读取或复制；关闭转发后容器/卷保留。原窗口第二备份及当前执行入口仍另行门禁。
新增文件：本目录 `rehearse157.py`，仅负责独立副本恢复/原Alembic在线演练与证据，不提供当前DDL入口。

首轮停在旧SSH端口60220拒绝连接，原恢复副本 current157-online-ad851b9b2e26 为已知151、无迁移intent。新增 `resume_rehearsal157.py`：仅消费该确切失败及完整151快照，当前 colima ssh-config 生成临时连接配置，不复制密钥、不重建/恢复旧副本；独立新journal记录六步。

## 零TCP窗口原生执行通道准备
原在线六步已通过，不以此代替当前维护。零TCP窗口仍使用原 `listen_addresses=''`，不恢复TCP来执行迁移。验证候选：本Task临时 Python sidecar 的网络为 none，仅将已核实 PG 容器 `/proc/<精确Pid>/root/var/run/postgresql` Unix socket 只读绑定为 `/pgsocket`，以及精确提交源码只读绑定；用原 Alembic 原生 psycopg 在线迁移。禁止写 PGDATA、不读取/复制凭据、不把待交付工作树导入。
先用当前 VM 已有 python:3.11-alpine 基础镜像构建本Task工具镜像，迁移依赖版本精确匹配当前已用且六步通过的宿主运行时。只下载依赖，不运行AOS业务、不改原PG镜像。记录镜像digest，先在隔离151新恢复副本验证 socket 连接、ROLLBACK及完整六步，再冻结当前入口；若通道不可用保留现场诊断并继续安全准备，不放宽TCP禁入。
新增 `socket_only_probe.py`：在已完整恢复的独立151副本，只读连接Unix socket，读版本/库/PG身份并rollback；加载原迁移图和157原模块，仅检查导入/目录，不升级、不写库。Docker工具容器network=none，PG socket和提交源码均只读挂载，精确检查PG PID/镜像/命名卷后才运行。

`/proc` 挂载被 runc 拒绝，无数据库连接。当前正式容器由公开 Docker inspect 暴露 overlay2 MergedDir；改用该确切目录下 Unix socket，只读绑定且network=none进行当前151只读预检，先核原源Id/原卷/PG控制系统标识，脚本 transaction_read_only=on 后读版本、rollback，不执行任何DDL/业务。此为已授权当前库只读预检，不代表隔离迁移通道已通过；当前迁移仍要求独立副本同通道全序列验证。

当前Unix socket只读预检已实际通过（r3原探针状态文案误带ISOLATED，原输出保留；intent明确为当前库只读，后续修正文案）。network none/readonly root/readonly socket/cap-drop ALL/no-new-privileges 下，原迁移图完整导入157，事务只读/Unix地址NULL/当前库151精确确认，零DDL。新增 `socket_migrate_one.py`：只接受152～157固定单步、固定DB、精确控制系统标识与前版本，原 Alembic 在自身 native transaction 内执行升级及157原审计；外层控制器必须先fsync intent再调用，退出码/后版本/全目录数据证明后才next。先新独立全恢复的151副本（source VM原镜像、单独volume、network none）逐步验证，绝不把当前只读预检当当前迁移授权。
新增 `socket_rehearsal151_157.py`：原源镜像在 source VM 新none-network PG/命名卷完整恢复首备份；仅该新库通过只读socket挂载的固定镜像单步执行152～157。每步外部intent/terminal/done独立落盘，旧602表按原行摘要算法分组核对；157原生迁移内目录审计原样执行，副本及卷保留。该验证不写当前库、不停止当前API/Web。

## 当前完整维护执行计划（原Unix单步隔离六步已通过）
新增 `current_window157.py`，仅固定本Task和原9cc容器/原卷/当前151库/HEAD5f0e4b5。依次：新私有claim/intent→精确原PID与子进程核对后SIGTERM→保存原listen配置来源→listen空并原PG重启→TCP拒绝/客户端0/prepared0→第二一致全备与globals/TOC→全新副本完整恢复及同冻结工具镜像原Unix六步演练→窗口内原全快照/HEAD/Task再核→原当前库6步逐项单次原Alembic升级→旧602表不变且私有新表空→恢复原listen来源并同卷PG重启→独立冻结提交源码API签名预检及8080启动→原Web8434启动→新进程/端口/健康/157/禁入/租户/快照核对→浏览器八页。无Provider/Host/worker开启。所有效果步骤先fsync精确intent，退出terminal落盘后再完整核对，未知不重发；失败保留封闭窗口、数据库卷/备份，不补done。旧151Task/固定历史执行器未改。
API使用已检查签名Receipt及当前提交的独立代码快照入口；工作树未交付Source/Profile模块不纳入运行。原Web源码未变，原plist和其他改动不覆盖。之后下一维护需按此新启动来源指纹核对，不再套旧固定API argv。

## 页面目录缺项最小修复
浏览器 RED：/v1/ecommerce-workshop/modules 因冻结源码根下 bundles 不存在而500。仅从同一HEAD git archive提取 bundles 到独立 committed-code/bundles，核每个文件与git blob相同；不读取商城源、不改变安装/租户/业务代码，不导入工作树。不重启PG、不重复迁移。重新读取目录及八工作台与Skill只读页面，再核数据与进程。
