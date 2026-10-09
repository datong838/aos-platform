# 根文件系统独占 native 测试库方案
Rules：用户AGENTS、AOS交付、231、原Source隔离验证合同。基线455b74ea/AOS-001636。原Task有效，唯一写者，无并行施工。资源路由读证：aos-extension data盘约2.5GB余量不能新增库，根ext4可用18280542208 bytes，MemAvailable2065000KiB。选择根ext4新独占目录 + docker local bind命名卷，不用mac虚拟文件系统或他人80GiB profile，不重启任何旧服务/VM。
精确新增仅本.evidence目录；外部资源仅新/var/lib/aos-test-labs/aos-source-root-native-20261009目录、新同名container与-data volume、新私有secret目录。VM父目录若存在先对账，不改旧权限。使用当前已验证本地镜像sha256:1a726528ec4ec3dfebf104148d3c6ae329828bfd228c305bb3e0e1e582ee074b，不构建/下载；新端口127.0.0.1:5437，1CPU/768MiB/no swap/128pids，SCRAM。当前真库和所有旧测试库完全保留不迁移。
写前冻结全部旧container ID/start/mounts/ports、root磁盘和内存、Task/Lease/HEAD；登记attempt后创建，每步保存精确结果，失败先只读对账不重放未知操作。权限仅新目录，根mappeduid100000用于新volume初始化；不得递归chown共享目录。原扩展control/sql与镜像native.so hash核验，template1安装有界原C验证器，真实签名positive与tamper-negative。新cluster独立，数据库模板无Source/业务权限。
验收新volume local driver Options精确bind独占path、PG fsync/full_page_writes/synchronous_commit均on、原镜像/版本/端口/资源边界、新cluster身份/独立volume、旧资源31+现有新增container全部不变；单节点预检留2.5GB及80MB新库预算。资源可用不授Source/正式业务权限。后续原distinct与完整native提交三个outcomes先精确新Task/原测试scope审计，未知效果不重发。不称全Source/COMMIT时钟/首链通过。

创建r1失败125：VM未挂载新host私有secret目录，daemon未创建PGcontainer；新root目录/卷/init container已明确产生、全部旧资源继续保护。采用已有旧lab受支持方法：仅创建新owned stopped container，把0600私有文件直接docker cp复制进去再start；不再重放目录/卷生成，不输出凭证、不用明文env/args。

新container首启动终止exit1，root新卷目录空且PG_VERSION不存在；Docker image VOLUME再次copy ownership70覆盖init501。仅新空卷按原注册修复chown501:20/chmod0700，然后启动同一精确container，不删除/重建，不动已初始化旧卷。

新cluster7694534063495901208/端口5437 native verifier真实签名正负向通过。基线仍455b74ea/AOS-001636，原Source测试文件无新改动，执行原待签完整shared/distinct两布局以验新资源和上一波未验布局，不把resource验证等同Source实际提交。所有新库独立retain，精确冻结七输入文件。
