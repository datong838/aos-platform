# W5b1 DS 配置恢复部分验收与停止（2026-09-24）

## 结论

**Config rev2 与 configure 正式成功；enable 未终态，W5b1 冻结。** 依 `w5b1-ds-config-refresh-plan-20260924.md` 的停止条件，不重发 stage/configure/enable，不人工启用定义或执行业务。正式库治理 rev13 不变，旧定义 disabled、新定义不存在，12 schedule disabled、活跃 attempt 0。

## 精确边界

1. 写前 DS active/etag5、binding rev9/epoch5 desired disabled/fenced、旧 Config rev1→Policy rev12、当前 Policy rev13、attempt0、canary0。单用途脚本测试 4 passed，`preflight` GREEN。
2. `append_configuration(previous_ref=rev1)` 一次返回同族 `5423ebf3-4928-4950-b55c-ea2662f84bc8` rev2/hash `sha256:3cb3fad905510dc90d38c4f03e3b504791139cc74330f235aa92f0cadb3f200d`；独立回读 PolicyRef rev13、previousHash 与旧 rev1 精确一致。私有 stage 文件 0600。
3. 正式 configure 请求一次，operation `5e92f8d1-0802-4382-a983-ee51c12c5b9a` 独立回读 `succeeded`；binding rev11/epoch6、desired disabled、enabled=false/fence=true、ConfigRef rev2。未打开 schedule。
4. 正式 enable 请求一次，operation `1d5b0071-3067-456f-8ab5-ee1f666abd83` 返回 accepted。按 50 秒间隔只读采样仍 accepted；其 deadline 2026-09-24T04:27:20.003484Z 已过，后续读取 2026-09-24T04:28:21Z 仍 accepted。唯一 `runtime-reconciler` outbox 消息未 delivered、attempt=0、claim_until NULL，表明未被领取；不能把接受 Receipt 当完成。binding 保持 rev11/epoch6 disabled/fenced，业务未开始。
5. 私有 `stage/configure/enable.json` 均 0600；8080 `/v1/health` 正常。当前状态是**已知的未终结 enable 边界**，不是未知是否发送：同一键已接受，严禁重复发送。脚本/单测与方案一致，但本波总体不得标 GREEN。

## 下一波 W5b1R

先只读诊断为何此唯一 enable outbox 无消费者（现有 8080 进程与独立 Runtime Host/assignment、Worker 开关、outbox lease），不接触凭据内容。根据正式 `RuntimeDisableService` 对“effect-free accepted enable”的原子取消规则，制定同一 DS 的有界 disable/settlement 或正式 successor 方案；先证明旧 enable 无资源/业务 effect，再通过 Owner Receipt 关闭它。不能仅因 deadline 到期自行删除 outbox、改状态或补发 enable。关闭后另立新配置/启用波，并确保真实 consumer 存活，绝不复用本波幂等键。
