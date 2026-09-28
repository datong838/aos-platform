# W5CB4 E17-k｜显式旧身份文件与当前签名安装同库门审计（2026-09-28）

## 只读代码路径

1. `a0v_ecommerce_runtime_host.py` 现要求显式 `--credential-file`，`_configure_environment` 检文件 0600/结构、bundle/trust 路径后设置固定 OCI context，并清除继承 DSN。它没有把凭据 DSN 的目标数据库同当前签名 Receipt 的安装库绑定。
2. `runtime_connections.py` 从保护文件读三条 DSN，核互异、文件权限/所有者；`production_runtime.py:select_production_runtime_host` 在同一个凭据目标库查 directory descriptors，再比较 Web/Runtime/Directory 的同一数据库 authority、三个非特权独立角色。该检查能拒三身份互相混库，但三者若一起指向**旧库**，同库条件本身仍可能通过。
3. 当前 `.aos-recovery-20260920` 历史三身份在 E17-b 已实际连接旧 `aos_meta_head`。当前新签名预检则绑定 `aos_current_preview_20260927@a0v_109`；当前该库 Host assignment 0、enabled identity 0。既有选择器若拿旧身份会读旧库的 assignment，不能当当前授权。
4. 没有实际调用 `_build_runtime` 或启动 Host；本波依据代码路径与先前目标库验证判定风险，不声称旧库目前能成功 materialize，也不尝试旧目录启动。

## 判定与下一最小方案

E17-j 消除了**默认**旧文件，但显式旧文件与当前 bundle 并列输入仍缺交叉绑定。下一波在专用当前安装启动前置验证器中使用受信签名 Receipt 解析当前 bundle/安装目标，分别以三身份做只读连接，比较同一个物理数据库 authority、角色互异/非特权，再只读核 `org-org/dev-project` 精确 Host assignment/Owner 与配置；全绿后才让原 Host selector 进入。验证器不能从用户传入的任意数据库名字自证当前目标，也不能打印 DSN/密码、启 Host 或写库。先文件级方案、RED，再最小实现。缺正式当前凭据时保持禁入。

当前真实库只读；Host/worker/Provider 关闭；浏览器 `browser-pilot` 截图及自然首链仍 pending。
