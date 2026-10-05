# 恢复副本原生SCRAM最小验证方案
Rules：231/AOS工程交付、原restore Task、m1单写。候选1隔离HBA缺口修复；候选2publication签名协议，选1。

仅固定colima-aos-a0v-test-only/current150-same-77f8f834ea15，none network/无映射端口/独立卷。复用当前未来Lease和精确Task、authority、HEAD及target检查。私有phase目录O_EXCL意图，未知不重试。

保存原HBA字节及模式；临时首行仅本库、本issuer、127.0.0.1/32 scram-sha-256，reload配置并检查解析。原issuer须NOLOGIN且NULL口令；临时设置SCRAM随机口令，经stdin输入私有0600 passfile，错误口令必须拒绝，再正确口令原生只读事务验证session_user=current_user=issuer、目标db、org-org计数及dev-org canary零计数。无审批事实写入/实际签发/完整Python连接器声明。

finally原字节恢复HBA并reload，issuer NOLOGIN PASSWORD NULL，删除仅本phase创建的临时口令文件，复核HBA SHA及完整13目录快照与a150一致。仅配置reload，不重启服务。任何异常保留intent/terminal、先只读对账。

执行代码目录：原restore证据目录/native-scram-probe.py；私有证据：aos-recovery/current150-.../native-scram-phase-20261006-0715；共享结果只写无密摘要。保护源库和其他容器，不push，不改Goal。

首attempt已终结失败并还原：错误口令拒绝，正确口令FATAL permission denied for database，issuer无CONNECT。SET ROLE不会检验CONNECT，不能替代native入口。r2须先复核原CONNECT false及完整快照未漂移，额外临时仅GRANT CONNECT本库TO issuer，finally REVOKE该直接授权；不授其它DB/table/schema功能权限。保存首attempt原终端，不覆盖或重发；r2独立phase和意图。验证后旧db_acl必须完整一致。
