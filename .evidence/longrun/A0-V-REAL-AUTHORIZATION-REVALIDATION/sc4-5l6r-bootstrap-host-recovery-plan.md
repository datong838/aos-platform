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

I create 已真实成功：ef5bc0c3-1dbe-4659-b839-2350f70232bf，approved/etag3，lock aa37071b59d7f9043bd743be03e46ea3e69b197f45bc2a77c798ba39f8b61cf7。命令最末输出位置与 create 内部结果文件重合，触发 O_EXCL FileExistsError；已只读核对主库和持久结果一致，未重发create。修正新profile的最终输出为已存在且内容完全一致时复用（已有输出的命令入口仍拒绝），避免成功动作被包装器误报失败。旧脚本不动。

07:44 I已完成verify/configure/enable：generation c26edf1c-5170-4158-9f30-36dc1f2ba07f，runtime4/epoch3 enabled/ready；config e9da1644-e00a-4ea2-8bac-0dc1429d339b@1/hash417d5ff383fe171626bdfd71322b66767ae975930ee4a4607ec18f12955860b9。H detach Receipt 0f3ee42d-1213-4a02-959f-dbb530feb586，实际组22（事件shrink20→正式disable fence21→detach22）。Host10096/API10098加载8de1d70f。
新增 `scripts/a0v_bootstrap_successor_business.py`，固定I安装和H detach exact引用，expectedGroupRevision=22，独立successor-i目录/键；新增 `scripts/a0v_bootstrap_successor_cutover.py` 在真实注册Receipt后固定其引用，逐阶段approve/prepare/pause/commit/validate/resume。沿既有服务和测试，禁止沿用H组16或伪造Receipt。

I successor登记已成功，Receipt e84d7f0b-ff5d-42e3-aa6f-9171f0675dc3，hash4bbbda6777ee9a56e35a14b982a9ab87c7f8dcb31cf173f9a1a7fabeaff5e4ce。外层结果标签沿旧包装器仍写CURRENT_H_SUCCESSOR_REGISTERED，但内层不可变Receipt和request均为I；不修改历史结果，新cutover以I的exact身份/hash校验。切换profile测试10通过。下一波使用I实际resume、独立健康与业务窗口，不复制H旧健康证明。
