# AR1-c 真实签名容器联合验收检查点

2026-09-06，m1，仍为内部运行基座验收，业务新增0。

专用VM公网DNS不可用，未修改共享网络；使用已有Python镜像建立测试专用只读本机Registry V2，将docker save的实际config/layer构造OCI manifest，按真实digest读取。没有公网推送，没有放宽RepoDigest或签名校验。

test_signed_real_oci_and_journal 专项通过：实际签名验证→真实RepoDigest→真实隔离容器注册与invoke→PostgreSQL持久领取和released回读。仍是诊断包/测试签名与证据，不是正式业务安装、业务port或安装终态。

Prime指出测试资源清理可能吞错，已修复逐项删除及独立回读，三个反证RED→GREEN；真实联合测试再次通过。累计约定回归exit0，6项既有warning及JDBC退出日志提示保留。对应359项测试切片，不代表全仓GREEN。

临时Registry容器与测试镜像逐项确认移除；原专用PG及共享Docker八个容器保持。无页面变更，浏览器不适用。下一切片记录实际容器ID与恢复审计；AR1-c继续。
