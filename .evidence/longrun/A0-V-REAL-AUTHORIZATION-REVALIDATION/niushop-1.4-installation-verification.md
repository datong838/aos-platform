# Niushop 1.4 安装配置连续运行回执

2026-09-12，入口基线cf12aeaf，Host基线e904c438（v15 PID98435）。实例afd792de-e85e-4680-86d0-c83404824fb3，Niushop1.4/domain1.3/growth1.7/operations1.2。

真实序列：reset approved@5→apply 12eff3e4-5d44-4f9e-a91b-7dc79cb2a4ac→applied@6→verify 2686692c-3f1e-4240-a721-18cdfe59128f→active@7；generation275e1941-2e87-4a75-aa3c-e0508be9e2ce。配置33b282ed-dbc1-4442-ac16-f3ff97202fd2@1 hash sha256:687d33543f93db03a5a736c54d66ccd7ccf2b68434f4b90db049d30ffc655bba，四来源正常授权；configure0a1b3203-e2dd-4e04-9255-253ef3065892和enable97f315dd-a6b4-4c3c-b25a-90c8b65867f8均实际succeeded。

14:29:47Z读回binding ready/enabled=true/fence=false@4，3容器running、资源pending未释放、canary0；elapsed497.816秒，原deadline14:26:29Z，续租7次。CONTINUITY_CROSS_INITIAL_DEADLINE_GREEN。14:29:53Z独立回读确认所有命令成功。此结论仅限该时点和安装连续性，非连续多日或业务场景完成。

测试配置/目标/真实PG代际27通过；closure ar2-7扫描1801、分类158、迁移93，hash/dependencies/reverse/crosslayer/dynamic五数组为空。未push，原历史目录和实例记录保持，主库a0v_023无DDL。主API仍旧进程，后续必须重载新root/凭据文件。P01仍未通过此波开启，也未进行源读取或业务派发。

下一波：受控读取适配器先claim独立提交，确认commit后单次读取，复用原Ingress恢复；仅created=true可读，历史claim但无Ingress判定结果未知不重读。精确当前mapping来自批准资产，先编译再占用，租户/配置/预算/角色和当前control重复校验。后续准备a0v_024隔离主库升级与API重载、SourceSelection/RuntimeControl、真实P01首链。经营计划与八工作台仍按真实业务验收矩阵推进；230L0挂起。
