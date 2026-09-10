# A0-V 真实文本 Provider 权威验证

## 结论

2026-09-10 在隔离恢复库 `aos-a0v-recovery-pg/aos_meta_head` 建立 A0-V 专用 Agnes 文本 Provider，并完成同命令重放。退出标记为 `A0V_REAL_TEXT_PROVIDER_AUTHORITY_GREEN`。

总依赖审计的首个未满足门已从 `providers` 推进到 `providerHealth`，下一动作是 `VERIFY_REAL_PROVIDER_HEALTH`。本结论不是 Agnes 实时健康、ModelRoute ready、Agent runtime ready、A0-V 总体 GREEN 或 A1 真实业务成功。

## 精确权威

- Provider：`ProviderInstanceRevision:a0v-agnes-text-readonly-dev@1`
- content hash：`66941c4bb51757f5d95a6149580f7bbb3dbe86debb2035747fa96229efb06982`
- plugin：`ProviderPluginRevision:agnes-text@3`，exact hash `124adf49e0ea6df5b2003e5bd32825863797723139757609d2f99af7f1e3dd0e`
- endpoint：`https://api.agnes-ai.cn/v1`
- region：`cn-approved-development`
- egress：`a0v-ecommerce-egress-v1@1`
- data classification：`a0v-ecommerce-public-catalog-v1@1`
- lifecycle：`active`
- Secret：数据库只保存 Keychain opaque ref；证据只保留 ref fingerprint 与版本 `a0v-v1`，未输出 payload。

Prime 的 GitHub Copilot OAuth 和 `~/.prime/agent/auth.json` 未被读取或引用，不属于上述产品权威。

## 首次、重放与隔离

| 检查 | 首次 | 重放 |
|---|---:|---:|
| Provider revision mutation | 1 | 0 |
| Keychain mutation | 1 | 0 |
| Provider invocation | 0 | 0 |
| business mutation | 0 | 0 |
| external publication | 0 | 0 |
| canary Provider revision | 0 | 0 |
| canary health observation | 0 | 0 |

独立 pre-mutation backup：`sha256:db40cd2fe1dda4d47d390ebec392b7dbdddc740a9a3847d50dcdc3f3a5a64fac`，4,357,116 bytes。

## 证据与验证

- 首次结果：`a0-v-real-text-provider-authority-result.json`，SHA-256 `e51290aafec0403f426f81afaa31dbea8847c458408ac034f43904d145d413ba`
- 重放结果：`a0-v-real-text-provider-authority-replay-result.json`，SHA-256 `ed147852ca3886388fafda1c787bcf82d143ced7bfd56f09434e953ae7c80680`
- 阶段审计：`a0-v-agent-runtime-readiness-after-provider-result.json`，SHA-256 `edaca014f3c2dc7e8a569d8d0baf01ad3b372ece898087459809742b3e4bc58c`
- 新执行器、Secret backend 与邻接纯合同：38 passed。
- Python compile 与 `git diff --check`：通过。
- 当前虚拟环境未安装 `ruff`，未将缺少可选 lint 工具冒充代码失败。
- 扩大的历史 Store 集成组中唯一失败连接硬编码的旧 `127.0.0.1:5433/aos_meta`；该服务在重启后未运行。本切片改用当前明确授权的隔离库执行首次与重放，生产 Store publish、exact dependency readback、Receipt 幂等和 tenant canary 均已实际通过。

## 一致性与风险复核

实现与修订后方案一致：默认 preflight、显式目标库、发布前备份、不可判定 Keychain 条目默认不覆盖、显式修复只作用于已确认异常的精确 service/account、Secret 经关闭 ECHO 的私有伪终端两次输入给 `security` 且不进入进程参数/环境/输出、数据库只存 opaque ref、canary fail closed、Provider 调用数为 0。

首次标准输入方案错误创建了空 Keychain 条目；v1 健康预检以 `secret_keychain_empty` 在 transport 前阻塞。随后 Security Framework 原位更新保留了不兼容 ACL，正式 resolver 仍安全阻塞。最终通过随机哨兵验证私有伪终端写入/读回 exact match 后，使用显式 `--repair-keychain-item` 删除并重建唯一异常条目。修复结果 `a0-v-real-text-provider-keychain-repair-green-result.json` 显示数据库 mutation=0、Keychain mutation=1、Provider invocation=0。

剩余风险是 Keychain 只证明精确条目存在，尚未证明 Agnes 当前接受该凭据；Provider health 仍为 0，必须由下一切片的一次有界真实探针取得短期健康观察。随后仍需模型/路由、Capability route、37 份 Skill 发布链、6 个 AgentInstance 与 ResponsibilityPlan，才可能关闭 A0-V。
