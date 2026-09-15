# 5L6R 新动作目录加载与正式运行恢复

m1串行，延续既有充分授权，不push，230 L0挂起。主库061、主仓d4591aa1；旧Host5448/API5449仍旧代码。H runtime6/epoch3 ready，组18，Policy5及源调度关闭，9 needs_attention/unknown和56pending保留，新目录0行。

## 方案与边界

1. 新增 `scripts/a0v_h_bootstrap_retirement.py`：复用G已验证的正式event lifecycle服务，固定H identity/generation/lock、实际Policy5 disable Receipt、group18→19 fence，再正式shrink到20。必须源停、策略全停，先exact审批再transition，每步独立幂等键/意图/结果。
2. 新增 `scripts/a0v_h_unaccepted_analysis_close.py`：fence后仅针对H的9条Policy5未接收初始化，使用060原服务验证原始来源、租户、目标Receipt不存在、确定性Run不存在、claim过期、当前fence精确引用，逐条不可变结案；56pending保留。先封入口→精确结案→再shrink，不先试失败shrink，不直接改状态或重放unknown。
3. 加载方式需以资源释放语义为准：Host stop 会关闭准备会话并释放持有资源，不能在运行实例上直接杀进程后假称ready。后续在完整排空后按正式disable/资源释放/dispatch detach及后继安装恢复，保持相同签名包、业务Case和现有模型版本；无需重新发布包。
4. 新运行加载后，刷新实际健康检查，采用新审批和新窗口启用Policy，验证目录自动建立。随后真实数据自然生成经营首链，保留人工评审边界和续跑证明。真实业务成功数未增加前不得报完工。

先测试H固定身份/组版本和未知意图拒绝，代码路径在主仓scripts及对应tests/extension_runtime。每波结尾留证据、提交、继续。

新增 `scripts/a0v_ecommerce_bootstrap_reinstall.py`：固定H→I恢复profile，沿已验证diagnostic_reinstall服务封装，旧H create结果来自host-diagnostic-recovery/install/h，新I全部意图和结果位于bootstrap-action-recovery/install/i。H runtime disable必须先完成event shrink（group20），旧实例释放、正式detach后才create I，使用同19签名包与替换引用；新增对应profile测试。不得覆盖旧G/H结果或复用旧操作key。

07:40实际状态：H fence Receipt a9eb9d13-c22b-4351-bc93-82e7c6d7243a（group19）；9条060结案全部完成；shrink Receipt eb47739a-e7ea-45cd-966b-3d5c031b3d69（group20）。disable 38d2fbec-4ef6-42d7-b2e9-df6c82e77331 succeeded，H runtime8/epoch4 disabled/fenced，3资源released且observed_release=true，dispatch lifecycle detached，H附着入口0。profile测试6+23通过。
加载流程：读取旧启动意图和PID，核对进程命令与H退休事实后记录stop-intent，发送SIGTERM并等待确认退出；新独立目录记录command及当前Git HEAD，启动相同launcher、相同签名根和信任根，只变状态输出路径；保留全部旧进程记录和日志。
