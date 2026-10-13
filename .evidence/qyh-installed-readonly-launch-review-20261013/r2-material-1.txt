# 原只读管理启动入口接入已安装目录

Rules：AGENTS、231、AOS工程交付、已授权栖月汇安装恢复。使用父Task原已登记scripts/a0v_qyh_restored_http.py和services/aos-api/tests/extension_runtime/test_qyh_restored_http.py范围，由当前同一写者串行施工。

最小方案：新增明确的--installed-readonly-installation参数，仅允许--serve-management-readonly且既有本机OIDC配置齐备。与正式--current-installation/--serve-limited互斥。Canonical UUID及固定org-org/dev-project；启动前复用select_current_installation核对当前真实安装/lock/Registry/签名，不自动选旧安装。只向被隔离过的子进程环境写非敏感AOS_INSTALLED_READONLY_CATALOG，不继承外部任意值。数据库仍default_transaction_read_only，原ReadOnlyManagementApp继续拒绝业务POST与WebSocket，不启动Host/worker/Provider。

RED参数/身份/UUID/互斥→最小实现→原入口与目录/API相邻→独立冻结资料复审→精确m1提交→冻结最新API与Web源码→只停止归属已核对的旧API/Web进程、保留同一PG/卷/IdP→原身份登录任务专属浏览器页，SPA八路由/菜单/只读负门验收。切换前登记意图、原进程与源hash；未知结果先对账，无数据库迁移/写入或整系统重启。

原目录实现13d532ebf已有73后端/20客户端/typecheck/build、真实签名8/隔离0、独立review2/2。此处不重复旧安装apply/verify，不把可查看当自然首链。
