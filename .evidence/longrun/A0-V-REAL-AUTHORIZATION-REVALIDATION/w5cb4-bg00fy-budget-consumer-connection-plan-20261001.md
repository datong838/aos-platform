# BG00FY 固定预算消费连接与准入计划

基线 AOS-001039 / m1 ad5d6e48 / a0v126。复习231总控、231-5费用与恢复、432接续、FX原子消费、FU schema门。7强一致CURRENT，validate1494/1492/3968。真实库未连接，本波不迁移、不启Host/worker/Provider。

## 完整接线顺序
FY完成独立消费连接与schema/function admission；FZ补原actor当前成员/只读原Receipt查询SQL（不能用写函数重放充当查询）；随后有限私有进程与一次attempt/unknown只对账，再接产品配置、真实Task预算risk联合验证和正式部署恢复波。自然首链仍pending。本波只交付前置连接，不宣称完整消费产品已可用。

## 文件级最小改动
- aos_api/pg_consumer_identity.py：抽取network已有低权限caller/owner/EXECUTE身份校验原语，调用者固定角色和函数，禁止从请求传身份；保持network合同/错误不变。
- aos_api/aip_network_consumer_connection.py：原require_consumer_identity委托公共原语，连接行为不改。
- aos_api/pg_authority_schema.py：抽取预算issuer现有catalog-only结构快照，显式表列表与函数owner映射，不复制hash或审批状态机。
- aos_api/aip_budget_cost_preflight.py：保持原公开接口和原manifest格式，委托共享快照。
- aos_api/aip_budget_consumer_connection.py：专域固定call/owner，仅loopback、精确dbname、0600私有passfile、无PG环境捷径，READ COMMITTED且scope固定正向，SQL限时，连接先catalog只读准入，再交付调用方；异常/commit未知不自动重试。
- aos_api/aip_budget_consumer_schema.json：仅隔离迁移126生成candidate审核后接纳。覆盖消费依赖表、列ACL、约束、索引、RLS、触发器及其函数、消费/hash/canonical定义。部署库不得生成自己的通过基线。
- tests/aip/test_budget_consumer_connection_pg.py：RED缺模块；真实独立LOGIN、精确身份和事务模式、一次消费/回滚、schema/函数/权限漂移拒绝、无共享API回退、配置变更和错误租户拒绝。复用已有隔离PG和TLSJWTfixture，绝非真实实例验收。

## 验证与退出
专项+network连接/预算issuer schema/预算原子consumer相邻累计，compileall、diffcheck；无UI改动浏览器不适用。核查原manifest输出一致、network旧边界不变、连接关闭和失败无新业务写。复审后verification、精确m1提交、Delivery/CAS/sync及D-waves登记FZ。回滚为代码回退且保留证据；本波无DDL或真实库副作用。
