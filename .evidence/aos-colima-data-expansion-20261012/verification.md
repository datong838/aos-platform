# 扩容前物理备份保护检查点

当前m1 04d0df92fb49621375cb1f7fec5f0fb60caab818；独立维护Task ACTIVE。七份备份SHA核验、成员无逃逸/链接检查、原生pg_verifybackup含WAL验证、实际隔离PG恢复启动及原system_identifier/数据库集合严格相等，7/7通过；隔离PG均正常关闭，验证容器保留。七个原容器CID不变且仍running，五个临时HBA独立再次SHA相等。

验证首轮脚本在读旧intent文件名时失败，尚未创建新意图或外部效果，已改用原正确文件名。随后Docker bind路径不存在exit125、inspect确认容器不存在，保留失败意图和日志；新r2流式输入避免依赖宿主目录映射，没有重放未知结果。Private日志/档案0700/0600，不提交备份内容或HBA。

现有Docker数据盘仍20GiB/100%，未停止VM、未扩容、未迁移真实159库。真实fresh159完整恢复Task仍未完成，不能用旧clone160演练代替。保护22项用户改动，无业务代码改动/no push。

下一步：冻结支持的临时库物理装载方式后才进行20→60维护；原tmpfs停止后消失，不能直接start让entrypoint新initdb冒充恢复。若需新恢复容器，须保留原容器/备份、显式对照原镜像/认证/网络/端口/cluster，并先完善本方案；不承诺保持新容器CID。然后最新当前159全恢复/权限/160迁移演练再继续真实安装配置八工作台。Goal active，全部业务退出仍未证明。

## 2026-10-12 12:46 最新维护验收

七个原镜像/原Env/原CMD物理装载probe通过；第三项真实HBA SHA负门拒绝Docker cp成功但live tmpfs缺文件，原隔离副本原HBA恢复并正常stop，改exec stdin并ready前SHA，五项新r2通过。原七容器停止保留，新七容器采用明确recovered映射；原四卷容器同CID/镜像/卷恢复。

真实源647全表指纹维护前与维护后均等于当前fresh159基线，两份当前dump SHA一致；维护前11个库无active client/ prepared xact；全部11正常stop，原profile正常stop/start、支持20→60扩容成功。vdb60GiB，data文件系统可用39625660KiB，默认Docker context不变，CPU2/memory3/rootDisk20保留。所有原卷和备份保留，无迁移、无旧Run/外部效果。11当前容器running；原7tmpfs停保留、新7 cluster/数据库集合/Env/HBA/网络/loopback ports全等。源原cluster7695302940039200809、aos_meta_head159、enabledBindings0、647全表数据等。

管理API18080与旧API8080 /v1/health200；Web8434 /200、18434/org/membership200。未更换API/Web进程与代码，这不是最新m1全系统重启、正式身份接入、安装配置或八工作台业务验收。仅独立容量维护可Delivery。fresh159原始完整恢复失败Task仍ACTIVE，下一新合法r2恢复须原失败无表回滚/新DB意图/原baseline全比较；随后目录/ACL/sequence/160门，不能从旧snapshot160演练跳转迁移。

复审：符合用户全系统恢复的容量维护授权及231数据保护；sameCID初稿在实施前修订为保留原容器/明确映射，实际验证其物理cluster和配置；没有绕过系统控件、未更新Codex、未改正式认证权限、未删卷/原备份。故障均在原运行时停止前复核，未知动作依阶段intent对账；源码AST/精确diff通过。长期Goal继续active，完整八工作台/自然首链/观察发布仍pending。
