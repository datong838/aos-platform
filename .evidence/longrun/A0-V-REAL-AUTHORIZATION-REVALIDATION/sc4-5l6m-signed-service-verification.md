# SC4-5l6m 独立连接签名服务验证

Rules：m1、先方案、隔离数据库、最小修复；不 push、主库不变、230 L0 挂起。

方案 85fc9e9f/0753c054；Task SC4-5L6M-SIGNED-SERVICE-20260916。

从标准临时 _ti4_test 库克隆专属副本，每例销毁；测试密钥签名的 growth 声明经 Registry validate/publish、Composition resolve/persist、Installation Store 状态与规范 evidence 保存。准备 active 安装、runtime 和九项分派是 fixture，不宣称 OCI 运行证明。真实 AIP decide 独立提交，非超级用户且 NOINHERIT 的 runtime/maintainer 会话调用真实 EventControlDispatchLifecycle。Artifact 读取使用真实 ManifestLoader allowlist 与文件 hash；未替换资格/审批/SQL/回执读取。

五种场景：正常 expand 与独立连接回放；合同文件篡改；审批人撤权；Receipt INSERT 抛错；SQL 期间批准过期。前三种故障原先正确拒绝，late_expiry 原实现 DID NOT RAISE，证明提交前复验缺口。

修复：回读时重算 Receipt 正文 canonical hash；在事务返回前再次调用既有签名资格及独立审批门禁。故障发生时新连接确认 Receipt 数量 0、分派仍为九项；解除故障后同 key 成功，再次调用回放唯一 Receipt、十项分派。最终 5 passed、7 既有警告、5.95 秒，退出 0。

关联回归：ProductEvent 300 passed、21 skipped（9.92 秒）；原 skipped 不计验收。memory validate GREEN，强一致 authority 仍 AOS-000573；diff check 通过。主库 E、新 Registry 和新安装均未改变。

边界：本文件证明 expand Service 独立事务组合；fence/shrink SQL、同步互斥、异步排空和 resumed 退役组合见各自专项。完整新版本部署、物理 OCI 生命周期及真实八工作台业务观察仍未完成。下一波：以当前提交重建/复验新版本包，并核对真实安装切换脚本的三个独立审批与失败恢复入口。
