# 本轮原卷完整重启方案

event 2026-10-09T01:07:59.537Z；HEAD0706f359ec344bf202bd155231d718fc01805e7c；authority AOS-001618。

先只读对账全部 Lease（同一Owner、无维护资源重叠）、既有已交付重启与当前实际API26897/Web27312来源、原PG9cc6091c/命名卷aos-a0v-recovery-pg-data及当前库157。从精确已提交HEAD冻结API/Web/scripts/bundles/packages，不带入未提交158/159；冻结迁移图头须157，签名预检失败则不停止服务。

新增本目录 restart.py，沿用已验收journal执行器，只替换本轮HEAD/authority/event/Task和实际已交付服务描述；把已知Web app依赖链接修复纳入准备。不改产品代码、不迁移当前库、不触碰原依赖。所有操作前核Owner/Lease/HEAD/卷/进程，intent O_EXCL+fsync；SIGTERM精确API/Web；同卷PG重启并核启动时间，签名预检后启动最新冻结API→Web；前后全用户表hash/public catalog一致；八工作台浏览器只读验收、租户canary403、安装与禁入门。未知效果先只读对账，绝不重放。Host/worker/Provider off，不能当自然首链。

新增范围：aos-platform/.evidence/current157-full-restart-20261009-010759；aos-recovery/current157-full-restart-20261009-010759，以及三项current-preview维护资源。完成精确Delivery并继续已登记跨调用方原计划隔离研究。

R1在任何服务操作前因已交付descriptor不含environment发生KeyError；claim及冻结源码已知完成，无stop/restart intent。R2只消费该已知准备结果，不重放冻结/claim；从原受控descriptor读取且白名单检查三项环境，继续首次签名预检及实际重启。保留R1错误。

R2精确停止API/Web后即时helper退出核查未通过；PG intent不存在。随后独立ps确认27313已退出、两端口空闲。R3只核对已知stop intent/PID退出、原PG启动未变、全数据一致，再执行首次PG重启，不重发SIGTERM；保留R2失败。
