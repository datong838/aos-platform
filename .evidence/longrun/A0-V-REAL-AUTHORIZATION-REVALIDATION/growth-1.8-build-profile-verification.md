# UQ5-B3c 构建配置准备

2026-09-13，基线ab072a46，m1不push。

固定profile：core1.3、niushop1.5、growth1.8、operations-base1.2；13API/8模块。默认通用builder仍12API及旧版本，新增可选session probe默认关闭。growth资格探针在同一会话2048次心跳后invoke固定只读方法，要求结果与冻结合同fixture逐值hash一致；失败进入原journal观察路径，正常记录probe_verified后released。

16项新旧构建/niushop profile验证通过，7项既有警告。探针fixture明确qualification-fixture-only-not-real-business，1Case/1Run，无数据库或真实租户写入。固定fixture SHA256 88d2e10d98ececd832bf6f4e07cbde53b1c5eae31be8ccb34dfe05cd77a3bdd9。

本证据仅构建准备，实际镜像构建与OCI资格验证将紧接此提交执行，使回执绑定已提交代码。原主库/Host/三个容器保持。
