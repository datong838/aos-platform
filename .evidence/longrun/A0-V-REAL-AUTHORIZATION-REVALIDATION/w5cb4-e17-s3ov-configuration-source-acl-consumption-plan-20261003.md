# W5CB4 E17-s3o-v｜配置消费时来源 ACL 漂移门

日期：2026-10-03。复习 231-3/5/9、栖月汇授权分层、E17-s3o-u 与原配置阶段消费事务。s3o-u 仅在 Host 选择时预检 ACL；启动之后若运行角色被授予职责 Plan/生产合同回执写权，原 `process_one_configuration_stage` 仍能消费。这一轮封消费前漂移，当前真实库继续只读。

## 文件级步骤

1. `services/aos-api/tests/extension_runtime/test_configuration_stage_consumer_pg.py`：隔离 schema 给真实生产 `ConfigurationStageConsumer.run_once` 构造非特权会话，先收窄三表 ACL，再模拟启动后 `GRANT INSERT` 到职责 Plan 表，RED 要求原请求保持 `requested`、配置行0。暂不把撤权后的消费成功当作本波判据：下述锁权限冲突须独立修复。
2. 仅在上述消费测试夹具补齐空的生产合同 Receipt ACL 形状，撤销职责 Plan 原测试迁移授给普通运行角色的写权；三来源表 FORCE RLS、运行角色只读。共享的 `current_configuration_sources_case.py` 不修改，以免影响其他真实来源测试；此夹具不证明正式签名。
3. `services/aos-api/aos_api/extension_runtime/configuration_stage_preflight.py`：从 s3o-u 只读 SQL 抽出可在调用者事务内使用的来源 ACL 检查，保留启动预检行为。
4. `services/aos-api/aos_api/extension_runtime/configuration_stage_consumer.py`：在生产 `run_once` 的原短事务处理待消费请求之前重验 ACL；失配抛出稳定失败、由外层回滚，不能将请求标 `rejected` 或伪造成功。保留原 primitive 的相邻事务测试，不把它当作正式 Host 入口。不得改四源内容读者、提交/Receipt 或自然 Host 配置。
5. 专项/相邻回归、静态、方案代码复审、verification；浏览器不适用于纯 Host 后端门。当前库无独立 issuer/ACL 收权，新门仍应禁入。管理员恰在一次校验后并发改权的极窄窗口，需正式发行/数据库 ACL 稳态与更强锁协议另证，不声称绝对消除并发授权竞态。

隔离测试只通过 `monkeypatch` 将模块内固定的 `public.` 三表名指向本次临时 schema；生产默认表名保持固定，不接受请求传入表名。测试夹具只在首次建好职责 Plan 后撤销运行角色的原写权，再创建一张空的 Receipt ACL 形状表，不用合成 Receipt 冒充正式发行。

RED 进一步发现旧职责 Plan 读取的 `FOR SHARE OF h` 在撤销 `UPDATE` 后报 `permission denied for table aip_responsibility_plan_head`。这是正式只读 ACL 与原四源读者的独立冲突。本波只证明生产消费入口发现漂移并失败关闭；撤权后正向消费不得宣称通过，后续须设计能保持版本稳定且不赋予 Host 写权的读锁/发行协议。

范围外：当前库迁移、启 Host/worker/Provider、旧 12 Run、商城源、230 L0。下一波专用 Plan/Receipt 发行与克隆 ACL 切换方案。
