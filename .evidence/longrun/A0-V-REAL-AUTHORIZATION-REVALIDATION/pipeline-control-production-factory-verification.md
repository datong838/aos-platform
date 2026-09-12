# 生产工厂与当前权限真实只读预检

2026-09-12，基线d3691ca7。新增pipeline_control_service.py：控制平面固定同一安装Store/ReleasePolicy，延迟按租户建立ManifestLoader和两层Owner；approve入口先匹配scope再使用原runtime_worker_connection/consumer_connection，额外检查两张历史表强制RLS与非owner身份。没有新角色切换、权限grant或登录流程。未开放HTTP、未启用P01。

工厂和原控制平面13项通过。真实只读预检首次10:33Z走过安装、当前配置四源、源版本与发布证据后，在读取manifest.exports发生AttributeError。失败证据保留pipeline-control-current-preflight-first.json。将测试替身改为实际BundleManifest结构后5项RED（19通过），修正为manifest.spec.exports；相关37项通过，10.04秒。

使用既有Host 0600凭据、原consumer_connection正式身份采用流程、已配置包根/信任根，10:35:38Z重跑scripts/a0v_pipeline_control_preflight.py：**currentChecksPassed=true**，ns_site/Shop/11列。固定原安装执行actor，原安装active@5、当前P01@1/源配置/当前配置/包内映射-schema-privacy均通过。证据pipeline-control-current-preflight.json。

本预检同步回调仅返回规格概要，**approvalsWritten=0、sourceRowsRead=0、businessWrites=0、executionGranted=false**。它证明当时当前权限组合可通过，不是永久许可，也没有检查SourceSelection/RuntimeControl新表的真实追加（两表尚不存在）。后续批准和执行必须重复当前检查。

AR2 ar2-7：1797/158/93，五类错误空；git diff --check通过。真实库权限只读盘点显示安装/绑定/配置/图/源读取所需权限存在，源配置历史仅SELECT，两张新表尚未部署。下一波按现有迁移Owner纪律备份、核对a0v_021→a0v_023确切增量和隔离恢复验证，再部署审批历史；随后接正式运行入口与原输入恢复。不push，230 L0挂起。
