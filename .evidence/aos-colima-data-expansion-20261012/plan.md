# AOS独立运行时容量维护方案

Rules231/用户全系统恢复授权/重启与接续职责分离，注册独立aos维护Task而非复用施工Task。当前Colima aos-extension VZ/CPU2/memory3/disk20/rootDisk20，data vdb20GiB满，hostfree55GiB，现目标data60GiB（比原80保留更大宿主余量），root/memory/CPU不变；--activate=false，不改默认Docker context。既有全maintenance Lease均回读，当前运行容器均AOS/QYH，没有启动或接管其他已停止实验实例；原gt-source Lease不删不夺，不修改230L0。

停止前必须保存全部运行容器精确CID/image/mount/tmpfs/restartPolicy与当前source159 volume/cluster；七tmpfs容器有历史实验数据，不能假定可以重建或丢失。优先pg_basebackup -Ft -D - -X fetch --checkpoint=fast通过现已有维护role Unix连接备份private0700/archive0600，含WAL且原system_identifier保留；每个intent先O_EXCL、result后hash/tar验证，任何失败不stop VM，不重发unknown。元数据只记录cluster、DB名称/数量/ArchiveSHA，不打印凭据或数据。当前volume已有两份一致dump保留，容量维护不执行数据库schema迁移，不开启Host/worker/Provider、旧12Run不调用。

全部tmpfs备份及恢复路径验证后，独立维护窗记录stop/start意图并只用colima stop --profile aos-extension（无force）/start --profile aos-extension --disk60 --activate=false支持入口。必须准备逐tmpfs同CID镜像恢复旧物理cluster而非新initdb重建；保持原true volume、全部卷/备份，恢复原running集合，其余stopped不启动。VM/start/restore未知只读对账不重放。源schema/cluster/org/volume/135历史安装再读，profile60及free容量、原API/Web连接验证后才结束维护。未完成前Task ACTIVE，不宣称恢复/8台可用。

本波文件仅本evidence目录plan/保存脚本/private备份/intents/results。所有真库实体数据不写，物理copy仅备份；不能因备份存在放宽正式身份/配置/预算/首链门。

备份门补充：首两个physical archive成功（446466560/55456256 bytes），第三stage-r2 local replication无HBA入口，在backup建立之前失败，runtime未stop。剩余如复制入口受限，仅owned实验container现有POSTGRES_USER维护账号local socket复制暂时放行，原HBA bytes+SHA保存private，reload仅该container；physical backup后finally恢复原HBA/reload/SHA核，archive旁保留原HBA，恢复启动前必须覆盖回原HBA（manifest验证需先于覆盖）。不修改real source、数据库role flags、网络HBA、实验业务数据；knownauth失败0字节artifact保留，以新r2 archive/intent执行，不覆盖或重放unknown。

恢复路径验证：新增verify_physical.py，仅本Task evidence目录。逐个使用原精确镜像、network none、无发布端口、rootfs只读、独立768MiB tmpfs，并只读挂载private档案目录。先核archive SHA/成员路径无逃逸和链接，再运行原生pg_verifybackup（包括CRC32C/SHA256与WAL）。验证后覆盖回保存的原HBA，使用原维护role启动隔离只读PG，核system_identifier与非模板DB集合严格相等，随后正常停止PG；保留container/日志/intent/result以便中断对账，不自动删除或重放。未全通过，不停止既有运行时。此项为备份可恢复性，不授予业务运行/正式发布身份或八工作台验收。

验证入口修订：首个run exit125明确bind源不存在且inspect无container，尚无PG/容器外部效果。当前VM未提供宿主工程目录映射，改为stdin流式tar送入专用tmpfs，无共享挂载；保留原失败intent/log，新r2 intent。原HBA作为明确忽略的维护文件加入stream，原生验证后移回原HBA位置，文件不在运行时留存。禁止根据宿主存在推断VM路径存在。
