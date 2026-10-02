# d2b3c4a 原 Stage Owner 与生成读者接线验证

方案：同目录 `w5cb4-gwb2c2c1b3c2d2b3c4a-stage-readers-plan.md`；上位231-5 §9。此切片仅提高新生成入口的原权威读取深度，不解除执行门。

1. RED：`test_ecommerce_content_generate_handoff_lineage.py -k accepted_stage_content_command_is_strict_and_host_stays_closed`，预期先查询唯一原 Review Receipt，实际立即 `accepted stage content Host is not wired`；1 failed/22 deselected，退出1。
2. 最小实现：新分支按 scope/Handoff 只读唯一持久化 Review Receipt 的17项 `sourceLineage` 候选；同事务以原 StageDecision/获批 successor 核8项 exact refs，再复用原 Case/Occurrence、Analysis Runtime、Stage runtime/Eval/permission 读者和当前 cutoff/expiry，最后调用现有新 Review Receipt 与 v3 Task/Brief 两读者。候选不能自行证明授权；`execute`/`verify_receipt`、Provider 和旧 Issue 分支均未放宽。
3. 隔离 PG 原 Owner fixture：无持久化 Review Receipt 时准确拒；有界注入的候选在原 Owner 真实表回读后，错误 Stage Artifact 在 Owner 门拒；原 Case/Occurrence Store 生产事实到位后，新生成入口与原 Review Host 一致停在缺 `AnalysisRuntimeReceipt`。有界候选注入仅测试接线次序，**不是持久化原 Receipt 或真实业务正向**。不使用 historical-event 绕开正式 G2 Eval 门。
4. 专项加相邻五文件：`103 passed, 7 warnings`，退出0；`py_compile` 与 `git diff --check` 退出0。原 Stage 正向完整 producer、双读者联合成功、当前正式身份/八配置/发布/assignment/绑定及自然首链均未证明。

复审限制：本波以未接线错误作为最后屏障；未来解除前须以真实原生产者在可销毁 PG 做 Stage runtime/Eval/permission、持久化 Receipt、v3 Task/Brief、可读产物和人工评审的完整正反链，最后再在当前正式授权实例自然验收。当前真实库只读，Host/worker/Provider仍关闭。

提交后运行回读：`m1@23097ad7`；`launchctl kickstart -k` 重载 API/Web，PID43654/43657。`/v1/health`、`/v1/ready`、`/aip/skill-publish` HTTP200；18181无监听。浏览器首次在重载窗口显示目录/候选读取失败，完整重载并等待异步数据后恢复：37项仅评测、已发布0、缺正式放行/Logic/路由三来源、“发布此修订”disabled、无电商工作台入口。该启动瞬态未当作验收通过，已复核最终页面状态。直接无 Bearer 请求 publication-options 返回401，符合预览认证边界，不能据此判定浏览器身份已正式齐备。
