# W5c6m Host 节点全集权威来源审计方案（2026-09-25）

上位 W5c6j–l：本机 launcher/受管目录/已知 DB 会话为 0 也无法证明全机唯一性；受管 lease 只能 fence 已登记 scope。当前可见 dev launchd plist 指向一个本机 Host；`deploy/spoke-full` 是可变 replicas 的另一服务模板，均非覆盖所有 Host 机器的控制平面清单。正式 closure 的 `FULL_MACHINE_HOST_TOPOLOGY` 仍缺。

## 文件级九步

1. 复习 `ar1_003` Host identity/assignment、W5c6j/l、dev launchd/compose/Helm、真实 closure 门与旧 Host 状态文件的证据边界。
2. 本方案先提交。本波只新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6m_host_fleet_source_audit.py` 无效应合同与 verification；不读取凭据、不改部署/Host/DB。
3. 合同区分“本机 launcher 配置”“workspace 受管 assignment”“动态数据库会话”“部署模板”，均不是节点全集的签名权威 manifest；不得把单份 plist、replicaCount 或当前 PID=0 推为跨机器 completeness。
4. 若将来建立可信来源，需绑定 exact 环境/cluster、所有可执行 Host 节点及启动身份、部署控制器签名/版本、禁用非受管入口、与 DB Owner 同事务读取的 fencing epoch；缺任一项仍 no-effect。
5. 专项静态测试加 W5c5k–z/W5c6a–m 累计回归；不做真实 side effect。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审：当前仓库未见能证明节点全集的权威机制，记为基础设施缺口而非继续产生本机零计数“接近通过”波；严格 24h 到线后仍须正式新计划/唯一 key/Owner 门/独立读回。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6n：切到不依赖真实 closure 的已知回归债，优先修复 `AOS_DATABASE_URL` 测试 fixture 顺序/旧 skip 可验证性；先方案再最小改动，保持 A0-V no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
