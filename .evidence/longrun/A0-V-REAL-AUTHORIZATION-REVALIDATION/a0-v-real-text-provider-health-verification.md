# A0-V 真实文本 Provider 健康验证

## 结论

2026-09-10 使用 `approval:AOS-000573:A0-V-local-readonly` 对 exact Provider `a0v-agnes-text-readonly-dev@1` 执行一次 Agnes 文本健康请求。请求返回 HTTP 200，延迟 483ms，总 token 59；AOS 写入 `ProviderHealthObservation:a0v-health-20260910160748912754`，状态 healthy，有效期 `[2026-09-10T16:07:48.912754Z, 2026-09-10T16:22:48.912754Z)`。

有效期内重放回读同一 observation，Provider call=0、health mutation=0。总依赖审计在 16:09:33Z 看到 healthy Provider 1/1，首个未满足门由 `providerHealth` 推进到 `modelRoutes`，下一动作 `ACTIVATE_EXACT_MODEL_ROUTE`。

本结果只证明该时点的开发 Provider 健康，不是长期健康授权、ModelRoute ready、Agent runtime ready、A0-V 总体 GREEN 或 A1 业务验收。观察过期后，任何真实运行必须按新的有界授权重新验证健康。

## 调用边界与输出

- 正租户：`org-org/dev-project`；canary `dev-org/dev-project` Provider/health 合计持续为 0。
- Provider/plugin/network/data/egress 均使用 exact ref；模型固定 `agnes-2.5-flash`。
- 固定无客户数据健康提示；max attempts=1、timeout=10s、max output tokens=32、fallback=0。
- 只保存 latency/token/response contract/observation metadata；证据 JSON 中 Secret、prompt、answer、headers、response body 均为 0 输出。
- Prime OAuth 未读取、未引用；电商业务 mutation=0、external publication=0、230 L0=0。

## 失败与恢复审计

1. v1 在 transport 前因空 Keychain 条目阻塞，`a0-v-real-text-provider-health-result.json` reason 为 `secret_keychain_empty`；Provider 调用实际为 0。v1 journal 保留。
2. 第一次 Keychain 修复因旧 ACL 无法由正式 resolver 读取，`a0-v-real-text-provider-keychain-repair-result.json` 安全阻塞；Provider 调用为 0。
3. 私有无回显终端先以随机哨兵完成写入、exact readback、删除验证；显式修复随后重建 AOS 条目，`a0-v-real-text-provider-keychain-repair-green-result.json` 为 GREEN。
4. v2 在 Secret resolve 成功后才写 `submitted` journal，随后完成唯一一次 Provider transport 和健康记录；v2 journal 状态为 completed。

首次 v2 结果中的 `healthObservationMutationCount=0` 是证据计数器缺陷：采集 `after` 时的数据库时钟比 Python observation timestamp 早约 2ms，错误地把刚写入观察排除。持久记录本身成功。提交 `74b9e9ed` 将计数改为 exact Provider 的持久记录总数差值，并在调用前关闭 `httpcore/httpx` DEBUG；零调用重放回读 `exactHealthObservationCount=1`，确认健康记录存在。

首次真实调用期间，`httpcore` DEBUG 在终端输出了响应 headers，其中包含短期 Cloudflare cookie；这些 headers 没有写入证据文件或产品数据库。`74b9e9ed` 已在任何后续调用前将 HTTP 日志压到 WARNING。后续不得以 DEBUG 运行含认证或响应 headers 的 Provider transport。

## 证据哈希

- v1 调用前阻塞：`a0-v-real-text-provider-health-result.json`，SHA-256 `278bfe8244f33d494412324a1711d556a2a38d95fd0759ac62f818296676ea82`
- 首次 Keychain 修复阻塞：`a0-v-real-text-provider-keychain-repair-result.json`，SHA-256 `8e8ca3f6ff9b23665a911f937daecdfc68a11f442628d09be43ecc6db3a80fd2`
- Keychain 显式修复 GREEN：`a0-v-real-text-provider-keychain-repair-green-result.json`，SHA-256 `4b614b2d5b190954046ddb5cd864e534670761e8cc5615b14a68a84a4b647fc6`
- v2 唯一真实调用：`a0-v-real-text-provider-health-v2-result.json`，SHA-256 `1ce3723fe90536092955c059ec0a2da2f158776367c0f9655288edf39c8cc05d`
- v2 零调用重放：`a0-v-real-text-provider-health-v2-replay-result.json`，SHA-256 `1609b6e485aa41a5da608b15dd4dcb9d489f80c62f9ca750f9332e3a29d4afda`
- 阶段审计：`a0-v-agent-runtime-readiness-after-health-result.json`，SHA-256 `44e91cfad6ef037e8220438312f60c08adff13efdb7ac66a4b24733dcb7ed2d2`

专项、底层探针与 Secret 邻接测试最终为 53 passed；Python compile 与 diff check 通过。已知测试退出阶段 JDBC logger 对关闭流的报错是既存清理日志问题，不影响测试结论。
