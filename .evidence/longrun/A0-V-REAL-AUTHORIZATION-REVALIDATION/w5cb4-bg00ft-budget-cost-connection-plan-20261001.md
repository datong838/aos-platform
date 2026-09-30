# BG00FT 预算签发私有连接接线

基线 AOS-001034 / 221cded6。复习 231-5 §5/6/7、公共产品契约、427、FS方案及network issuer connection/process/IPC。原FT包括连接、schema、IPC、产品恢复，完整范围保留；按依赖先交付本波连接工厂，后继FU做精确schema部署门与独立IPC，再产品原请求恢复及原子消费，不把子项通过当正式签发/首链完成。

## 文件级实现
- 新 services/aos-api/aos_api/aip_budget_cost_connection.py：固定aos_budget_cost_issuer，显式loopback/port/db/private pgpass配置，绝对路径；仅复用现有network配置的路径/字段校验器，不复用network登录authority，不修改现有network路径。禁止PG环境密码/service/options回退；每次连接前重验凭据权限，不读取或输出密码。connection 5秒、SQL10秒、锁5秒、事务idle10秒；read repeatable-read/read-only，write serializable。
- 绑定配置的TenantScope，工厂拒绝别的scope与非bool read_only；连接事务开始执行FS _db身份角色/权限/隔离检查，另核current_database及三个timeout。没有默认API/owner DSN；connect失败只给稳定码。SET LOCAL在commit/rollback后失效，因此复用一个预算专域wrapper恢复scope并重新验身份与超时；两种事务都覆盖，连接退出关闭，不自动重试、不commit业务之外的写。
- 新 services/aos-api/tests/aip/test_budget_cost_connection_pg.py：复用FS真实隔离角色临时LOGIN/private pgpassfixture以获取测试地址，实际工厂连接；真实TLS JWT approve/Inquiry/revoke，DB默认scope/权限/timeout与commit/rollback、只读DML拒绝、SQL/锁timeout真实取消，错误scope/配置/凭据权限变化/PG环境污染拒绝、错误database与timeout漂移、网络域凭据不能取得预算authority。无Owner/session_user替身正向，fixture权限只隔离测试库。

## RED与验证
先缺模块RED，后专项 + FS/FR/FQ及network连接相邻累计；compileall、git diff --check。无UI改动，浏览器不适用。当前真实库零连接/零写/零迁移，无OS身份部署/Host/Provider。精准m1提交与Delivery/CAS/428/D-waves/Prime。

## 复审/剩余风险
本连接校验不是schema完整性证明或正式OS隔离证明；schema预检、IPC peer身份/帧限额、unknown原请求持久标记和产品恢复必须在正式入口启用前齐备。即使代码通过也不将凭据配置进共享API。原factory核心可由隔离测试提供，但生产组装只能通过独立进程固定配置。正式库迁移仍独立备份克隆零窗口。
