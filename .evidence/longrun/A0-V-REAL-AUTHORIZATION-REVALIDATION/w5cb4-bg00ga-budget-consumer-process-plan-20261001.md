# BG00GA 有限预算消费私有进程

基线AOS-001041/868b131a/a0v127；复习231-5、434、预算issuer有限进程、networkconsumer显式CLI/私有配置、公共peer/frame/listener。7强一致CURRENT。当前库只读、不迁移/启Provider/读商城源/重放旧Run。

## 文件级计划
- aos_api/aip_private_process.py：从预算issuer抽取纯配置边界、固定execute_once/inquiry帧解析、kernelpeer先行的一次连接处理与有限accept循环；不复制另一套状态机，不含业务SQL/尝试Receipt。
- aos_api/aip_budget_cost_process.py：上述公共片段委托，原签发dispatch及连接预检不改，原测试累计保护。
- aos_api/aip_budget_consumer_process.py：固定BudgetConsumerConfig+org-org/dev-project、不同API/consumer OS UID、socket父0750/凭据父0700文件0600、attempt0700。启动先externalOIDC/私有目录/只读DB身份schema，再bind；每请求scope/currentJWT由FZservice重验。固定有限连接数1..64和等待<=30秒，异常只返回固定blocked，不泄露JWT/SQL。只清理自己创建且未被替换的socket。
- 同模块CLI `python -m aos_api.aip_budget_consumer_process --mode check|serve --config <absolute private json>`，复用私有无跟随文件读取，exact字段拒绝重复/未知项；check不bind不消费，serve有限运行。参数错误不回显敏感值，输出ready/accepted/processed不冒充业务通过。
- tests/aip/test_budget_consumer_process.py：RED缺模块；实际隔离PG/TLSJWT的dispatch，原请求重建只读恢复；启动拒绝OIDC/config/权限drift且socket不存在，sameUID真实内核拒绝、有限空闲退出、替换socket保留；CLI配置和参数脱敏。当前未具备不同OS UID的正式正向链，不伪造该验收。

## 验证及退出
专项+预算issuer process/FZservice/FYconnection+相关IPC累计，compileall、staged diff，verification/精确提交/Delivery/CAS/435/D-waves。无UI改动browser不适用。下一BG00GB接产品自然消费投递/只读恢复，及合法development价格/预算政策producer与真实Task风险联合证明。当前127正式恢复另波做身份/备份/克隆/零窗口；本波不部署正式账号或后台进程。
