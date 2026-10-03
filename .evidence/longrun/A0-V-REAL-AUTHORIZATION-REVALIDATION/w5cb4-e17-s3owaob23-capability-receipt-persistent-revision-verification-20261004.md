# E17-s3o-w-ao-b23｜Capability Receipt 结果版本落盘与最新栈验证

## 方案、RED、最小改动

- 231-4/BIND-1 与 b22 对照，先提交文件级方案 `m1@547ef47b`。共享 `_insert_receipt` 被 AgentInstance 及 Capability/Skill/Run 等继承调用；本波仅增加可选 `result_revision=None`，普通调用与旧回执 JSON 不变。三类 Capability 操作均在原事务 `RETURNING` 后用**实际** `row['version']` 生成结果版本，不新增表或迁移、不从客户端 expected-version 伪造结果。
- 原独立 issuer create 基线 `1 passed`；新独立测试断言 create Receipt 结果版本时 exit1，`None != '1'`。最小修复 `m1@aae68ee2` 后，`tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_aip_binding_readiness_service.py` 合计 exit0，`25 passed, 1 xfailed`；create/evaluate/update 三处版本与 Binding 实际版本一致，旧 b22 无配对伪造仍 strict xfail。
- 相邻 `tests/aip/test_aip6_002_registry_receipts.py tests/aip/test_aip6_003_exact_instance.py tests/aip/test_aip6_capability_run_handoff.py tests/aip/test_e17_s3oo_capability_reader_pg.py -k 'not downgrade'`：exit0，`19 passed, 2 deselected`。`py_compile` 四个改动 Python 文件、`git diff --check` 均 exit0。
- 扩大合跑曾得 `20 passed, 2 failed`：旧迁移测试要从当前 `a0v_135` 降到 `aip6_001`，当前迁移主动抛 `shared schema receipt ACL cannot be silently widened`；单独顺序复跑仍同一失败，与本次无迁移改动无因果。Agent control 用例合跑时观察实例13而非旧断言6，单独复跑 `1 passed`；属于跨测试共享夹具顺序污染风险，本波不修改既有断言。一次并行单跑还使两测试库同时 ALTER 全局角色产生 `tuple concurrently updated`，已改串行复核；不能以并行错误冒充产品缺陷或回归通过。

## 权威卷最新代码重启及浏览器

- 重启前 `m1@aae68ee2`、`docker --context colima-aos-extension inspect aos-a0v-recovery-pg` 显示挂载权威命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；`BEGIN READ ONLY` 回读 `aos_current_preview_20260927/a0v_135`。独立完整恢复演练备份 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261004-s3owaob15/current-full.dump` SHA256 `e9038a51cee401e280d9dcfe4422f533cdb2fb407b00bd37bb21b6b5879bf498` 与 b20 记录一致。当前签名 Receipt 预检 exit0：approved、4 published、runtimeBindings0、库/代码迁移头135。
- 精确 `launchctl bootout gui/501` API/Web 两个 LaunchAgent 后 `lsof` 查8080/8434无监听（exit1）；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0，`pg_isready` exit0，读回同库/同迁移头；再精确 `launchctl bootstrap gui/501` API 后 `/v1/health`200，bootstrap Web 后页面200。新 API/Web PID `68097/68121`，18435/8080/8434监听、18181不监听；Host/worker/Provider未开启。
- `/v1/health`、`/v1/ready` 与八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 均200。内置浏览器重载 `/aip/skill-publish`，选择栏显示 `org-org/dev-project`，37条仅已评测/发布0；当前精确发布候选三阻断、发布按钮 disabled，侧栏“暂无可见工作台入口”。浏览器截图已在本轮 CUA 工具输出可见；未保存成本地 PNG，不虚构文件路径。当前库 `BEGIN READ ONLY` 再证 Receipt6/CapabilityBinding0、Reader/issuer正式角色0。

## 复审结论和后续门

- 方案与代码一致：仅 Capability 三类新 Receipt 增结果版本，其他 `_insert_receipt` 调用继续默认 `None`。旧回执回读与幂等重放原样保留；本波没有给普通 runtime 新权限，也没为缺少正式 issuer 的当前实例打开写入口。
- 此修复是**持久版本前置**，不是生产 operation-scoped Receipt 防伪。b22 的双向守卫只有 test DB，`xmin` 不是正式持久协议；正式 issuer/Reader/OIDC/Owner 与迁移/回滚仍需单独安全施工。当前真实库只读，八配置/六 Binding/Host/自然首链 pending；b20 五类 Capability 写503继续禁入。
- 下一波 b24 核共享 Receipt 全 operation/发行者权限与持久同事务配对方案，在独立测试库 RED/最小 guard；正式当前卷切换仍需新备份、完整恢复和零执行窗口。不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
