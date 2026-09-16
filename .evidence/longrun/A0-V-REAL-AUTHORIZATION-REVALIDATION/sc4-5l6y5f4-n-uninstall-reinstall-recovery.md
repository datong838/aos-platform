# Y5f4-N 卸载重装与准备中断恢复证据

日期：2026-09-16

代码基线：`d27f6d44`
租户：`org-org/dev-project`；`dev-org/dev-project` 仅作零可见 canary。

## 结论

`J_K_FAILURE_RECOVERED_L_READY_UNROUTED`。J 已从 disabled/detached 状态正式卸载；第一次后继 K 在 apply 成功后因旧 Host 退出而失去 PreparedJob，系统没有复活资源或绕过验证，而是通过正式 preparation-reset 将悬挂 verify 终态化，再正式卸载 K。第二次干净安装 L 已由持续存活的唯一 Host 完成 prepare、verify、四源配置和 enable，当前为 active / ready / enabled / unfenced。

这证明了真实卸载、重装以及“准备成功后 Host 中断”的恢复链。九条业务路由仍保持 legacy fenced，尚未把业务流量切到 L，因此本波不把“安装恢复”误报成“自然经营首链恢复”。

## 固定身份与状态

- J：`d6531562-e388-4206-a3ba-a89aaddc255c`，revision 6，`uninstalled`；原 generation `5295b81e-6005-4c2e-befc-3323f1456b8c` 保留历史，binding 为 stopped/fenced。
- K：`6dcae78b-a1e9-402c-ad09-36b111f52698`。apply 成功后旧 Host 退出，三资源被正式释放；verify `5837a0ed-3859-4fe1-b1c4-2d722e7c1a15` 到期仍 accepted。`RuntimeLifecycleService.reset_preparation` 生成 preparation-reset 证据，将 K 回退为 approved 并把 verify 标记 `PREPARATION_OWNER_LOST`，随后 K revision 6 正式 `uninstalled`。
- L：`19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3`，lock `sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8`。
- L generation：`64742c68-5e71-485b-a3c8-edc20be3d101`；binding revision 4 / epoch 3 / enabled / unfenced / ready。
- L config：`e02eeab5-eabf-41b5-82ee-47229b938e2f@1`，hash `sha256:f98af03c9790f56b50a08d8d876a0b019390225d51577e8fdf0926f775bd1ff4`；角色、数据、预算、运行策略四源均通过当前授权校验。
- L 四个 operation（apply、verify、configure、enable）全部 succeeded；三项资源仍归当前 Owner 持有，未被回收。

## 无副作用边界

- 数据库仍为单头 `a0v_072`。
- J detach Receipt 仍为 `15f04808-68e3-481f-9e20-9c6cf43a49a8` / `sha256:da0fbd2e59fc3176274eade80acbdd58f2bce8fdbf24b29843b334c76c0c0f98`。
- 九路仍为 legacy、fenced、revision 20、group revision 35；尚未注册或切换 L。
- running=0、claimed/unknown=0、canary=0；schedule 未启动，event-control 未启用，externalEffects=0，businessRunsResumed=0。
- Runtime Host PID 87185 在最终快照时存活，状态为 `RUNTIME_HOST_ACTIVE`，唯一正租户为 `org-org/dev-project`。

## 实现与验证

- 新增固定 J/K/L 恢复执行器，所有写动作都有不可变 intent/result、固定安装身份、CAS/etag、当前授权与未知结果不重发门禁。
- 方案在发现真实 Host 中断后先补充 preparation-reset 分支，再实现 reset/create/uninstall/L lifecycle；没有数据库直写运行时状态。
- 执行器失败关闭测试：12 passed；扩大 current-reinstall + preparation-reset 回归合计 40 passed。
- 最终权威快照：`sc4-5l6y5f4-n-final-state.json`；它同时断言 L ready/unfenced、三资源 live、四 operation succeeded、九路仍 fenced、零 inflight 与 Host 存活。
- Python compile、`git diff --check`、Alembic single head `a0v_072` 通过。AR2 closure verifier 仍报告清册既有 hash/dynamic-reference 漂移；本波未修改所列漂移文件，因此继续作为独立清册债务保留，不把它误报为本波失败或最终关闭。

## 下一波

以 L 的 generation/epoch/configRef 和 J detach Receipt 为固定输入，编写 L successor registration 与九路原子切换方案及执行器；依次完成 register、prepare、pause、commit、validate、resume。切换完成前不启动 schedule/event-control；切换后先验证九路全部指向 L 且零自动业务 Run，再提交本波证据并进入真实事件入口恢复。
