# 已交付独立实验库的保留与运行资源释放

Rules：先方案后脚本，本目录 retain.py；唯一 m1 写者，沿已批准恢复维护、231保留数据和归属对账合同。候选 A：已完成实验库资源保留/释放，依赖 exact 同线程旧Task Delivery、当前新Task Lease、无其他施工或连接、命名卷保留；候选 B：原 Source reader 兼容分析。选择 A，不凭TTL或名称夺取其他资源。

已找到原 Task qyh-source161-clean-maintenance-lab-20261012 的真实 Delivery（同owner codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2），原scope维护目录同本新Task且无重叠未解决 Lease。原创建/迁移合同与当前inspect共同绑定 CID52cc28f30197cc4010bd0167139e849e239591d7d9c47023ebcb36ac06164e7c、cluster7695744911813242913、原PG image、network none/无端口、唯一命名卷 aos-qyh-source161-clean-maintenance-data-20261012。该资源不是当前栖月汇权威PG或登录服务，也不是仍需运行的Source capacity clone。

先native只读获取cluster、非template DB目录和无其他active/idle-in-transaction连接；原同owner Delivery须存在。逐个非模板库新完整custom dump和globals --no-role-passwords，private700/文件600、每个第二份SHA相等、原pg_restore --list成功，native目录再核无变化且连接归零。所有意图O_EXCL，既有意图/未知stop只读对账不重发。然后仅原精确CID docker stop，保存 stopped terminal、inspect原命名卷仍存在且未删除、所有archive SHA仍等于备份，读取当前VM MemAvailable。停止不等于演练所有业务完成；原命名卷保留全部实验数据，备份保留，无其他container/卷/原服务/Goal变更。此波不启动新的恢复或Host，不以释放少量内存宣称足够完整恢复。
