# 栖月汇当前Host OID原维护入口接续

Rules：用户已批准恢复/可修复漂移，231-4审计与恢复、原Task qyh-full-system-restoration-20261011单写scope；当前org-org/dev-project、原命名卷不替换、不重启系统、不启用Host/worker/Provider、不push。候选A为已通过独立全库restore的当前Host OID原CAS维护；候选B为Source reader/Plan锁耦合隔离兼容；选A。新增代码仅本目录current_host_oid_maintenance.py，必须原SQL维护函数，不改产品源码或历史行。

依赖证据5364b6ba5及qyh-host-oid-durable-full-restore-20261013/verification.json，独立持久卷650表/roles/membership/sequences与原库相同，schema只有两条精确AND结合律重组；原CAS1→2及重放/冲突反例已验证，原650不变。执行前再次核父Task Lease、最新authority与原CID/volume/cluster/a0v161、全部executionbindings disabled、无执行事务及API无businessPOST/HostOFF；new pg_dump/globals双份校验与650表有界read-only指纹。

当前identity exactRole aos_a0v_directory_20260912与host a0v-local-ecommerce-host-20260912，expectedRevision1，原storedOID203325与liveOID16385漂移。原extension_runtime_bind_host_identity(name,text,boolean,bigint,text,text,text)权限/Owner以及正式维护channel必须真实核验。维护actor记为已授权本线程恢复执行者，不能冒充人类Owner/审批人。新idem key/hash绑定当前identity和备份SHA，先exclusive intent，原受支持函数CAS事务提交；任何未知结果只读查receipt/history，不重发。

完成必须currentroleOID回读一致、原revision1历史保留、仅三张Host表变化、其余647表全hash不变、序列与schema/roles unchanged；绑定仍disabled、HostOFF。后续独立正式三平面身份配置、最新m1API准备接线部署与原installation apply/verify门继续，不能称八台已恢复。
