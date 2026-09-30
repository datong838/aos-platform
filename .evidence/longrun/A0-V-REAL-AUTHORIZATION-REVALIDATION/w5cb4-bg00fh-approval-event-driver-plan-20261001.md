# BG00FH 精确批准事件消费处理器

m1@c71bb722/AOS-001022；Task W5CB4-BG00FH-20261001。复习231-5§3/5/7、公共产品契约§4、415，读issuer/action store/consumer application/service/contracts/a0v122。

## 事实缺口
Action.decide同事务写持久approval_event/action_event；现有consumer只由显式HTTP入口调用。a0v122要求外部OIDC subject精确等于原maker且当前成员合法，不能用checker JWT或API共享主体替代。没有已核验的持久事件订阅/后台maker身份来源。不能为了自动化复制或持久保存人类JWT。

## 本波文件与行为
- 新aos_api/aip_network_approval_event_driver.py：处理一个明确proposalId+approvalEventId，不全库扫描、不凭客户端hash消费。入口先检ConsumerApplicationConfig和外部OIDC实际签名/精确scope，再用aos_runtime、readonly/repeatable-read连接读取同租户精确持久事件及提案；只接网络action、approved且checker!=maker、事件hash/binding一致、原maker认证相符。由权威行构造NetworkConsumerReferences，交既有execute_consumer；后者与独立consumer继续做最终时效/成员/目标/事务门与持久防重，驱动器不是授权裁决器。
- 不复制最终expiry/receipt裁决，以免历史已执行事件不能只读对账；重复事件由原marker改为Inquiry，不发第二次Command。
- 新tests/aip/test_network_approval_event_driver_pg.py：真实隔离PG+TLS/JWT验证权威ref解析、重复事件、checker/其他maker/crossscope/过期token/错误事件拒绝、错误DB身份拒绝。IPC capture仅合同证据，不当实际消费通过。

## 不改变的现场边界与待接线
不新增HTTP消费按钮，不注册后台任务，不启动Host/worker/Provider，不迁移或写真库。该处理器是未来已授权持久事件订阅器的单事件入口；可靠订阅/ack、合法原maker服务身份来源、正式部署及真实自然消费留后续，不能把本波称自动链完成。旧12Run不动，230 L0挂起，m1单写不push。

## 验证/收口
RED→最小实现→新专项及相邻consumer/issuer/atomic PG累计→方案复审→verification→精确commit/Delivery/CAS/416/D-waves。无UI变更，无新增浏览器完成声明。下一BG00FI先复核持久事件投递与正式身份供应合同，按现有方案选择最小接线，禁止以复用checker凭据或后台扫描历史全部事件代替。

复审验证补充：新增真实consumer服务/PG Receipt组合用例，仅将IPC transport桥接到原服务函数并注入提交后响应丢失；原TLS/JWT、受限DB角色、原子消费函数和Receipt都真实执行于隔离测试库。重复事件只能Inquiry，head/revision/receipt各1。此证据不覆盖真实Unix socket和正式实例事件订阅，不称自然首链通过。
