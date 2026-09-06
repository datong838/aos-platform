# AR1-c 持久资源新进程恢复检查点

2026-09-06；基线m1@8115818d/AOS-000537。主Lease继续，本检查点不关闭AR1-c。

ResourceJournal增加1..100有界游标候选和installation→operation→binding→resource锁内复核。ExpiredResourceRecovery只使用可信宿主独立IDLE连接，原runtime角色/RLS守卫、租户范围、1秒锁等待及10秒SQL超时；session advisory独占覆盖先提交fence/uncertain、后OCI和记录观察。租期在锁内按DB时钟重验，未领取撤销不触引擎，已领取缺失/异常保持unknown，不重发创建许可。精确context/name/owner及已知containerId匹配后按不可复用ID删除，另代binding不改变。

测试：22Red→29passed8.70s；补删除已发生但DB观察回滚→新worker仍uncertain、等锁期间续租→拒绝引擎调用。真实OCI发现旧Docker缺失错误大小写识别问题，1Red→归一后仍False（不是删除成功）。专项84passed17.96s。新增全新Python子进程只接收临时schema与持久resourceId，从账本恢复真实OCI并清理，原driver/owner内存不传入；1passed/21deselected15.61s。实际创建/删除仅专用colima-aos-extension；未启动业务处理或Provider。

最终累计802passed、6既有warnings、117.18s、exit0，安全测试集合同上个检查点。git diff --check通过。既有JDBC关闭日志流警告不影响exit0。独立Prime增量只读复审未发现新问题，非其重跑测试。无页面改动，不冒称新增页面浏览器通过。

所有DB测试仅18432专用PG临时schema，清理精确容器ID；共享数据库、真实业务数据、外部发布和费用不变。只证明单资源重启安全收敛，不是业务任务自动续跑、整代卸载完成或物理可插拔最终完成。新增业务场景0。

下一段自动进入有界资源批次与准备操作失败收敛，确保全部确认释放才结束未提交准备，不能改写已提交成功的历史；随后正式broker、预算hold、持久派发与完整生命周期。
