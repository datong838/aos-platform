# Source 累计共享内存修复隔离实验室
Rules：231、AOS交付、唯一m1写者，不push/正式库/Host/Provider。
已登记候选：原Source386累计与实际finalCOMMIT截止反例；先修累计环境局部失败。旧r3终态341PASS/1setupERROR，127库7已提交Source独立审计通过、77资源未变，但backend signal11自动恢复，完整386仍RED。
文件仅本目录create_lab.py/install_verifier.py/lab.json/run专项及累计/只读审计。新独立owned容器aos-source-desktop-shm-20261009、新命名卷同名-data、5441，完全相同原生C镜像，shm256MiB、总内存768MiB无swap/1CPU；不重启/删除任何旧资源，不复制旧库或未知效果。创建每步intent+receipt，失败只读对账；SCRAM私有passfile、耐久on；前后两引擎所有原容器ID/StartedAt/挂载/端口不变。先原失败节点freshfixture专项，再整个386 freshfixture累计不筛选；资源峰值取样，不通过删除库/清统计造绿。
根因已证实64MiB POSIX共享内存容量耗尽，分配33554432失败；具体子系统暂未证明，SQLAlchemy调用psycopg.connect已确认不能声称绕过。扩大新实验室容量直接解除已证实限制，剩余内存上限/增长/crash风险持续观察；不声称修复PG崩溃根本缺陷或Source真实截止门。

创建器遗漏已知volume-nocopy修正，exit1空卷权限失败；独立readonly卷审计确认无PG_VERSION且完全空。保留旧failed容器rename，现有空卷仅chown/chmod，再新显式nocopy容器，无旧DB重发。

专项exit0/1PASS17.26s，原fixture新建库、迁移不跳过。独立只读审计后启动原386集合r4 freshfixture；每节点记录真实shm容量/使用，至少32MiB可用，否则setup显式RED。资源门不替代业务断言、不禁统计、不删库。

Terminal receipt: entire386-terminal-green-independent-readback-complete. Bounded evidence delivery only; actual COMMIT deadline remains pending.
