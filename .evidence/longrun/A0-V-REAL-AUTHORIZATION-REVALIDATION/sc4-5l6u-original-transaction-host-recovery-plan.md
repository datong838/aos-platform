# 5L6U 原始事务修复的正式加载

前提：主仓e27ce884，主库061；I Policy6 revision2 disabled，源schedule disabled；9 unknown/56pending；当前Host10096/API10098尚无最新修复。m1串行、不push、230L0挂起。

新增 `scripts/a0v_i_transaction_retirement.py`、`scripts/a0v_i_unaccepted_analysis_close.py`：固定I安装ef5bc0c3-1dbe-4659-b839-2350f70232bf/generation c26edf1c-5170-4158-9f30-36dc1f2ba07f/runtime6 epoch3；读取实际暂停恢复Receipt（analysis-pause/lock-recovery/result.json）。原Lifecycle精确审批fence24→25，060原服务逐条证明并结案9条Policy6未接收，shrink25→26；保留56pending和I动作目录历史。

新增 `scripts/a0v_ecommerce_transaction_reinstall.py`：固定I→J，前序create来自bootstrap-action-recovery/install/i，新目录original-transaction-recovery/install/j。正式disable后等待资源release/dispatch detach到28；核对旧PID命令后SIGTERM并等待退出，新进程加载e27ce884及后续脚本，不改19签名包。J identity必须来自create结果，然后按prepare/verify/stage/configure/enable。下一波实际注册及切换、健康、权限、业务窗口继承Case，Policy6→7。严禁重试unknown或手改历史状态。

复用既有已验证服务，测试固定identity、generation、旧intent、精确组版本及资源释放条件。每阶段记录实际Receipt。

08:02事实：I fence Receipt340cd03c-54e2-4d6c-b57d-140d83c9449b/group25；等最后claim于23:59:48Z到期后9条060结案完成，shrink Receiptfb8c96fa-fb80-414a-8691-b218881d509b/group26。正式disable已完成，I runtime8/epoch4 disabled/fenced，3资源released且observed_release=true，dispatch detached。旧10096/10098正常退出，新Host12960/API12961加载03bf562f（包含e27ce884核心修复）。正在逐阶段创建并准备J。
