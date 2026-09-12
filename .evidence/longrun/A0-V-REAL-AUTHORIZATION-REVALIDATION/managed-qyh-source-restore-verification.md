# AOS托管数据源恢复实证

2026-09-12，基线15693cd9。jdbc密码helper原代码直接拼接单引号，隔离fixture先复现原样输出失败；改为shlex.quote+printf，密码SSH路径StrictHostKeyChecking=yes。68项连接/注册/探针回归通过，diff check通过。未改私钥路径或已有进程清理合同。

定向重载18181 API后，先读Sources空集合，再经POST /v1/sources正式登记org-org/dev-project niushop-qyh，type jdbc-mysql-ssh、runtimeMode direct。返回200，configurationRevision=a84b6c79-8654-48f0-98c2-57d41b067b3d；GET唯一回读，公开响应无password/sshPassword/config/props/secretRef。输入取自原项目.env，在进程内提交，不写请求文件或输出凭据。

06:39:46Z正式/test同revision返回200、ok=true、2111ms、302表、未截断。AOS临时SSH监听63714，探针结束后监听已消失，未借用外置13306。仅查询当前配置数据库的information_schema，不读客户或商品业务正文、不写源库。

再次定向停止API PID66969并同脚本重启；06:41:23Z GET同revision、/test再次200、ok=true、1630ms、302表。这是独立的重启恢复验证，不是未知调用重试。服务会话42042，日志在仓库外api-managed-source-restart-verification.log；独立Host与两前端未停。

IAB tab10 5173/data真实显示1数据源、栖月汇微商城、MySQL SSH隧道、直接连接、上次同步为空。页面“在线”不是SourceReadiness全绿；实际同步/管道尚未恢复。12数据集显示也不能视为12管道真实同步证据。

证据：managed-qyh-source-registration.json、managed-qyh-source-probe.json、managed-qyh-source-after-restart.json。下一波复习现有P01–P12正式配置/Mapping/Schema/Masking/SourceReadiness Owner，先恢复商品与店铺链的受治理管道，再自然调度和只读对账；不运行含reset的旧初始化脚本，不调用直接返回SUCCEEDED的空同步facade。固定九项调度登记访问范围仍独立，230 L0挂起、不push。

限制：现有本地Source Owner私有props保存执行配置，未完成生产Secret Manager引用化，不能因此宣称生产凭据治理完成。本波未把秘密写进证据、日志或Git。
