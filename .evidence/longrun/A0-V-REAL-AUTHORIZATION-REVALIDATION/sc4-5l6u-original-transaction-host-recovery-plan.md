# 5L6U 原始事务修复的正式加载

前提：主仓e27ce884，主库061；I Policy6 revision2 disabled，源schedule disabled；9 unknown/56pending；当前Host10096/API10098尚无最新修复。m1串行、不push、230L0挂起。

新增 `scripts/a0v_i_transaction_retirement.py`、`scripts/a0v_i_unaccepted_analysis_close.py`：固定I安装ef5bc0c3-1dbe-4659-b839-2350f70232bf/generation c26edf1c-5170-4158-9f30-36dc1f2ba07f/runtime6 epoch3；读取实际暂停恢复Receipt（analysis-pause/lock-recovery/result.json）。原Lifecycle精确审批fence24→25，060原服务逐条证明并结案9条Policy6未接收，shrink25→26；保留56pending和I动作目录历史。

新增 `scripts/a0v_ecommerce_transaction_reinstall.py`：固定I→J，前序create来自bootstrap-action-recovery/install/i，新目录original-transaction-recovery/install/j。正式disable后等待资源release/dispatch detach到28；核对旧PID命令后SIGTERM并等待退出，新进程加载e27ce884及后续脚本，不改19签名包。J identity必须来自create结果，然后按prepare/verify/stage/configure/enable。下一波实际注册及切换、健康、权限、业务窗口继承Case，Policy6→7。严禁重试unknown或手改历史状态。

复用既有已验证服务，测试固定identity、generation、旧intent、精确组版本及资源释放条件。每阶段记录实际Receipt。

08:02事实：I fence Receipt340cd03c-54e2-4d6c-b57d-140d83c9449b/group25；等最后claim于23:59:48Z到期后9条060结案完成，shrink Receiptfb8c96fa-fb80-414a-8691-b218881d509b/group26。正式disable已完成，I runtime8/epoch4 disabled/fenced，3资源released且observed_release=true，dispatch detached。旧10096/10098正常退出，新Host12960/API12961加载03bf562f（包含e27ce884核心修复）。正在逐阶段创建并准备J。

J create实际已成功，d6531562-e388-4206-a3ba-a89aaddc255c/approved3，lock85f986267d34c4847b7045144a61539a7f57abfc75ac582721b27e6b3cd5d785。后置输出比较仍报差异，进一步定位是create封装返回额外旧outcome字段而内部持久结果没有该字段；原O_EXCL问题的同值复用不足以解决它。新J profile改为返回完整原始create结果，使内部/外部持久输出同一结构；不改已存在文件，不重发create，主库只读核验后继续prepare。

J已完整prepare/verify/stage/configure/enable：generation5295b81e-6005-4c2e-befc-3323f1456b8c，runtime4/epoch3 ready，confige2fdde1f-ebdb-4863-b158-7204735f3fe8@1/hash91ca4b1b840890be7c664edcac37f4b7ca76bddc29e3549e90dd9c679d32c0c5。I detach Receipt5edd5f6b-3d8a-486f-a280-aedf720b59cf/hash8f114365450506d285258669ba7e63c36630091422fa815a7a7b2d1ff656d168；group28。
新增scripts/a0v_transaction_successor_business.py、scripts/a0v_transaction_successor_cutover.py，固定J及实际I detach/注册Receipt，expected28、切换core29；所有结果使用J标签，保持I历史不变。新增同类profile测试。下一波当前健康、权限、Policy6→7及event组30真实观察。

J真实注册Receipt94223205-b6fe-496b-97de-fff8c765297a/hashd9412d150fc3ac70c71e64f5b6e08adfad809189cd11baf7e90676841eebfe02。恢复profile23、注册12、切换10检查通过，正在正式六阶段切换。J创建结果输出结构已统一返回原始create结果，旧I/J历史结果均未改写。
