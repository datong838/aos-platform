# DNS真实修复验收

真实RED：原quay.io拉取[::1]:53拒绝，VM /etc/resolv.conf悬空链接且systemd-resolved不存在；主机DNS223.5.5.5/Registry401成功。保存原悬空链接备份，再原子替换仅VM DNS文件；未重启Docker/VM/PG/API/Web或改全局配置。getent实际解析成功、固定原镜像实际pull全部checksum完成，repoDigest cde8d7fff48622d7bff959ea2a98e945ae8a7ccb0117b44858de77243b96231e。

相邻真实验证：原栖月汇/v1/me仍scope org-org/dev-project；权威PG同卷/StartedAt12:25:24.538保留，无源卷变化操作。修复不等于身份服务健康、AOS接线或8台通过。身份服务另Task首次Java构建内存压力故障已单独停自身新进程处理；没有删演练库或重启原库。方案与实际文件/权限/备份/作用域一致。
