# W5CB4 当前 AIP 定义 durable intent 写入器计划（2026-09-27，编码前）

## 目标与限制

- 承接 `366e96c4` 的 EMPTY/FREEZE 只读门，下一步只实现**受控命令**，先隔离验证再决定是否对当前新库执行。23/28 项测试不能代替真实 53 行写入或运行准入。
- 231 A0-V/BG-00 与栖月汇 9.3 要求精确来源、版本、证据、失败关闭。Runtime Host/worker、商城源、旧 Run、Provider、配置/预算/审批不属于本波。

## 文件级步骤

1. `scripts/a0v_current_aip_definition_publish.py`：默认只读 `--preflight`；必须显式 `--execute --intent-id <固定 UUID>` 才可开始。写前以当前签名 Receipt 调用 preview exact DB/signed tree 门、RegistrySnapshot/TrustRoot 双签名读取；构造仅指向 `aos_current_preview_20260927` 的显式 `connect_factory`，绝不继承 shell 的默认 AOS_DATABASE_URL。
2. 在当前 signed state 旁以 `O_CREAT|O_EXCL` 建唯一、不可复用的 intent 文件，内容仅目标 DB、签名 hash、bundle identity、intent id、开始 UTC、预期 6/37/10，不含凭据。**先持久化 intent、fsync 文件和目录，再触碰 Owner DB**；任何已存在 intent 无论状态都只读冻结。若创建失败/崩溃，禁止重发。
3. 写前只读锁定三表目标键全空，并核 0 Runtime binding；若非 EMPTY 停止。按 Owner 10→6→37 单次调用当前 verified adapter，异常不重试。写后用显式连接逐键回读 ID/revision/source/hash 与返回 refs exact；任何缺行/多行/错误即 `FREEZE`。不自动补行，不把部分提交当成功。
4. `services/aos-api/tests/aip/` 新增当前专用隔离 PG 和故障注入测试，覆盖目标库误指、intent 存在、签名漂移、空/部分/已全量、各阶段异常、最终 exact、旧版无回归。当前 preview 仍维持原实例且不自动重启；需要重启看新投影时另按安全预览计划读回 Cron=false、worker=false、第二 Host=0。
5. 通过专项、累计、浏览器/HTTP、方案一致性复审后写 verification，再 m1 提交。只有完整受控命令与隔离故障测试 GREEN 才讨论当前库一次执行；执行后的 verification 与 git commit 独立封存，不以脚本“尝试执行”算完成。

## 本波停止条件

- 当前库任何定义行非零、intent 已存在、目标 DB/签名/Receipt 漂移、无法确认真实连接工厂、历史夹具缺目录、未知写入边界，均只读报告并停在该边界。不得换 intent id 重试或手工 SQL 补齐。
