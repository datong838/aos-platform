# 本轮提醒142→150最新全栈重启方案

提醒aos于2026-10-05T15:42:01.797Z在唯一thread正式到达。m1 b4727d82/authority1356，真实current aos_current_preview_20260927@a0v_142，colima-aos-extension/aos-a0v-recovery-pg/原命名卷aos-a0v-recovery-pg-data/18435；API PID7130/8080、Web PID7155/8434、Host18181无listener。唯一Alembic head150已提交，无本轮待测进程。不是Goal历史135。

先restore-only Task w5cb4-current150-restore-gate-20261005-154201：新增scripts/a0v_current_150_restore_gate.py和scripts/tests/test_a0v_current_150_restore_gate.py，复用原142的canonical snapshot/backup hash/私有文件/原bootstrap连接读取，不修改原142executor。真实私有0700/0600目录新consistent exported REPEATABLE READ snapshot全备+无密码globals（原生产角色密码不复制）；恢复到独立test-only context新无网络/无端口固定镜像/不同新命名卷，精确比全库旧行、sequence、角色/成员/DB ACL/config、RLS、函数/ACL与元数据。保留所有源卷/备份/目标。

逐步原143..150 offline SQL生成/hash/intent→实际transaction执行→回读单head；不启LOGIN、不业务seed、不Provider调用。每步源current无DDL。固定代码HEAD、当前库/卷/镜像identity；unknown outcome原journal对账，不能改Task/runid盲重发。

预期变化必须由原迁移代码冻结：a146/a148各增加独立容量申请/SourceReview metadata；a143 Health epoch、a144 publication epoch、a145容量request、a147候选与a149 neutral epoch新增表，原历史表行/序列不可改变；a144 evaluator原窄授权/强制RLS/a150私有读锁授权及七原trigger PUBLIC EXECUTE撤除按精确清单审计，不能笼统忽略ACL变化；原runtime正常trigger compatibility已单独测试，新角色全部NOLOGIN/noinherit/nomembers/no高权。已有neutral/health/publication backfill须按实际migration原文审核，不能一律假设新表空。

恢复门GREEN后另登记当前维护资源Task；先精确原服务argv/cwd/启动时间/listener/child/UID和签名receipt回读，再停两原服务、原PG listen空重启/hostTCP拒绝/现client0/prepared0、停写第二份可校验一致全备和第二独立恢复、逐步迁移当前原库142→150、精确旧行及权限预期变化复核、恢复原listen来源并PG→最新m1 API→Web、八工作台浏览器核心只读/安装/租户/禁入。现142runner写死版本与authority，须新正式维护实现和RED/相邻/完整隔离演练后才操作原源，绝不替换常量绕过门。若失败按私有journal已执行阶段只读调和再修复，不改变Goal。

Host/worker/Provider仍关闭；签名安装/禁入预览200不等于正式首链。此Task不交付真实重启/迁移，完整提醒验收及后继publication研发继续待办。
