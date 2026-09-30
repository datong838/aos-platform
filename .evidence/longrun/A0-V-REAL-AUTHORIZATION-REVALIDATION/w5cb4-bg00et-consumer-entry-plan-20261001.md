# BG00ET 显式消费者入口方案

基线 AOS-001008/m1@c96ef59c。复习 231-1 四层边界与首链依赖、231-2 隔离运行与签名、BG00EM actor/Receipt 服务及 BG00ES 配置预检。不改业务权威、JWT、幂等状态机或安装状态。

新增 services/aos-api/aos_api/aip_network_consumer_cli.py 和 services/aos-api/tests/aip/test_network_consumer_cli.py。

入口 python -m aos_api.aip_network_consumer_cli --mode check|serve --config ABS_PATH --preflight-org ORG --preflight-project PROJECT。所有参数必填；禁止缩写、重复参数、额外参数，无默认运行。解析失败输出固定错误码，不回显传入内容。CLI不支持JWT、密码、DSN、SQL或临时角色参数。

构造 typed TenantScope，读取私有配置后强制只读预检。check只返回ready/businessAuthorized=false；serve只有预检成功后调用已有有限连接/有限空闲等待进程。预检scope仅校验DB上下文，不构成接收请求的租户授权；每次请求继续原JWT/actor/tenant/current approval门。返回统计明确不是业务成功；异常固定错误码并退出非零，不重试、不后台化、不启其他worker。

RED以真实子进程启动缺失模块；GREEN覆盖help、缺参/重复/未知参数且错误不回显、真实私有文件和隔离PG只读check、真实空闲serve并清理自己的socket、占用路径保留与预检失败无listener。无identity替身的进程组合测试，但测试配置仍不是正式OS独立身份/IdP/来源验收。

正式环境保持禁入：真实库只读，119–122未部署；不读商城源、不重放旧Run、不手工run_definition、不push、230 L0挂起。下波核对正式部署所需OS/ACL/身份来源及未接线产品入口，不能用命令行测试冒充首链。

## RED 后发现的导入边界
原入口 RED 9 failed/66.45s，缺模块；真实子进程发现 aos_api/__init__.py 提前 import main，独立消费者被迫载入全部 Web 路由。补登记 IMPORT 子 Lease，仅修改此文件为 PEP562 按需 app/create_app 导出，保留 logging 初始化及 __all__。新增真实子进程断言导入包/CLI不加载 main，并验证历史 from aos_api import app,create_app 仍等同 main 导出。此变更为独立入口必要依赖，不改 Web app 实现。
