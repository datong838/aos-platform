# Niushop1.5 替换实例批准与回读

2026-09-13 03:49，代码cc18753a。先前无效前驱3项RED，修改first-install可选CurrentInstallationRef后原有/新增11 passed；原API launcher2 passed。只读replacement预检确认旧1.4@7 enabled ready/binding4/epoch3，归属旧实例最新绑定计划enabled0、unstopped0。新API profile只读check通过，仍localDiagnostic=true、productionWebIdentityComplete=false，不冒充生产Web身份。

实际19:47Z create/submit/approve后新实例eda57424-b8cb-401e-a6f7-94220cb4f9ef approved@3，Composition9244d05e-0ec6-424f-a73a-a82e5cec7d97@1，lock sha256:26e8189ca75d124fe49b27c5e6922a5115071e8f2a7e126c904e3949e4539f59。四坐标core1.3/Niushop1.5/growth1.7/operations1.2；明确currentInstallationRef指向afd792de-e85e-4680-86d0-c83404824fb3@7/旧lock/原overlay。沿既有本地测试maker/checker独立actor，不声称真实双人审批。

独立只读回验新实例approved、active_revision null、lock及前驱exact一致，runtime bindings0、operations0。尚未发送prepare，不会让旧Host读取新包。安装记录7→8，正租户7→8，canary0不变；Source/Provider/经营Case/Run未执行。执行前完整主库备份4,784,132字节，sha256:196a2c93e85bf12b42531232bbe6555d2bdbd0131820b7b3f19e877db1f5ea01，仓外私密保留。initial JSON路径：.aos-recovery-20260913/state/niushop-1.5-replacement/approved-installation.json。

下一波沿已登记维护替换方案：补固定目标disable-parent/prepare/verify/observe命令并先固定提交；通过旧Host完成disable/排空，确认disabled_committed后才TERM旧Host，确认释放/退出，再启动新Host与新API基线。不得并发两个Host；旧头active历史保留，旧代禁入；然后新实例prepare/verify/configure/enable。P02实际读与nullable详情仍后续，当前不能报替换或首链完成。
