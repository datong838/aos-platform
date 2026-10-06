# 隔离测试池容量修复

Task aos-test-pool-disk-capacity-20261006，同thread owner，AOS-001410，lease7日12:00。唯一物理scope colima-aos-a0v-test-only data disk；证据本目录。正式aos-extension上的aos-a0v-recovery-pg/权威named卷、API/Web不操作；全部数据库/卷/backup不删除，default Docker context不切换，不提升C verifier256MiB内存，也不提升测试VM2GiB内存。

故障事实：main测试库CREATE DATABASE报DiskFull，测试data ext4/vdb1 15G/14G/33M avail；C verifier容器原id63c7d47b、image a0eb61b312f9、volume aos-ed25519-test-31dccb3dc27e-data退出，WAL recovery因no space无法extend，OOMKilled标志true另保留。主机78GiB可用。Root COMMIT/rollback/两种epoch竞争3/8.84s此前成功，当前最大输入测试还未进入其fixture。不得重发未知登记。

顺序：只读保存全部container inspect/volume identity/known Root testDB names、两profile差异及colima原配置hash→graceful test-only stop→colima原profile start仅disk30/activatefalse→只读df/disk/profile/context及volume集合/镜像/内存/network对账→原C容器同volume启动恢复（不建新卷），独立回读3个已知Root库hash/epoch/rootcount及原template无root schema→专项后才继续当前最大输入。若驱动/分区不能扩，保留已有存储并诊断；不绕过格式化/删除或清空。此Task不推进AOS自然首链、不触发正式重启、不改Goal状态。

目标路径仅由受支持colima工具管理：/Users/ddt/.colima/aos-a0v-test-only/colima.yaml，/Users/ddt/.colima/_lima/_disks/colima-aos-a0v-test-only/。不手工改宿主虚拟磁盘块或其他profile配置。
