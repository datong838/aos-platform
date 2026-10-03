# s3o-w-ah｜六 Agent 来源与激活绑定到期时钟门

## 上位方案、现时来源与边界

复习 231 主计划 §首链、231-9、BIND-1 §2/3/3.4；六数字同事需真实当前、tenant scoped、可用的 CapabilityBinding，激活时用服务端现时重验，不允许将旧快照或目录定义冒充运行资格。当前真库只读：六 Agent 均 provisioning、active0，六个 published AgentTemplate 的来源都是 Growth1.11，CapabilityBinding0。当前安装的签名 Growth1.13 存在，但仓内 1.11/1.13 的 six-coworkers、capability catalog、37 logic 与 AIP policies 四项内容 SHA256 逐项相同；AIP 定义发布器显式冻结候选为 1.11。不能仅凭包装版本差异改写不可变模板或批量升级六 Agent。正式 Binding 依赖与身份仍缺，当前实例禁入。

新发现的最小风险：`AipAgentInstanceActivationService` 在激活入口接收 `occurred_at` 并用它比较 `readiness_expires_at`；即使同事务锁住 Binding，若激活处理到写入时快照已经过期，旧入口时间仍可能放行。HTTP 入口传服务器当前时间，但事务排队或锁等待可以使其变旧。这是已登记“激活时新鲜”合同的独立代码切片。

## 文件级计划

1. `services/aos-api/tests/aip/test_aip_agent_instance_activation_current_binding_pg.py`：在可销毁 PG 库补确定性 RED，传入预检时点早于 Binding 到期、写事务时 DB `clock_timestamp()` 已过期；旧路径错误激活，期待新路径拒绝且 Instance/Receipt 不变。保留现有撤权、锁与幂等正例。
2. `services/aos-api/aos_api/aip_agent_instance_activation_service.py`：只在原 Store 写事务的锁内重查读取数据库现时钟；到期比较不得早于此时钟。保留原预检和原 Receipt/CAS、公共请求不变。不在当前真库写。
3. 运行专项/相邻回归及一次性 PG 正反、编译与代码/方案复审；记录验证并 m1 精确提交、AOS/Prime/D-wave 收口。若签名 Growth 定义内容比较不能证明正式发行，明确限度，不更新候选常量或生产身份。
