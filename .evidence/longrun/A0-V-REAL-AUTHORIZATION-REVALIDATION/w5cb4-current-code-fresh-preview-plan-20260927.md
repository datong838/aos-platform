# W5CB4 当前源码新实例预览与启动修复计划（2026-09-27，方案先行）

## 目标与当前事实

- 用户要求立足当前最新 m1 代码重新实操、启动 AOS 供浏览器验收；不再追索误删卷或旧签名目录，任何已有数据、库、卷、容器、备份和文件都不删除。
- m1 `4524c369`，现有 8080 API 运行在已保留的 `aos_fullstack_preview_20260927` 隔离库 `a0v_106`，8434 前端可达。页面目录却报 `MANIFEST_INVALID`，旧签名包目录与信任根文件缺失。原 `aos_meta_head` 仍是 `a0v_092` 且 Runtime unknown/fenced；不得直接用新代码接原库或开启自然 worker。
- 源码候选已到 growth `1.11.0`、Niushop `1.23.0`、core `1.4.0`，而 `build_ecommerce_current_candidates.py` 仍固定 growth `1.9.0`。当前源候选是 unsigned/unbuilt，不能冒充已发布包。

## 文件级清单与串行步骤

1. RED：补构建 profile 专项测试，要求解析 m1 源码中的最新明确版本、实际注册 operation 集合与清单一致；验证旧 profile 不被伪称当前。修改限 `scripts/build_ecommerce_current_candidates.py` 与对应 `services/aos-api/tests/extension_runtime/` 专项。
2. 最小改动：只修当前 profile 版本与正向约束；不改 Bundle 签名校验、Installation/Runtime 权威或页面的权限门。发现源码候选不满足可构建前置，列精确缺口，不伪造 image index/evidence。
3. 安全构建：现有 builder 会 `shutil.rmtree` 清理临时目录，违反本轮无删除要求。须先新增显式 retain-all 运行模式及测试，覆盖正常/失败路径均不调用删除；只用新唯一私有输出目录，保留全部中间物。若 Docker build/资格检查还有隐式删除，停在静态测试，不运行该命令。不得改其他旧路径默认行为。
   测试基础夹具 `services/aos-api/tests/conftest.py` 也会自动 `DROP DATABASE`；先增显式 `AOS_TEST_RETAIN_DATABASE=1` 路径，跳过 terminate/drop 并输出可追踪的测试库名，之后每条 pytest 命令都带该开关。原 `disposable_database()` 夹具另有 DROP，在改成保留模式前不跑对应测试。
4. 新实例：在**另一个**新建、保留的隔离库中用最新 Alembic 建结构，通过公开 Registry/Installation/Runtime 控制路径构建签名包、信任根与安装；签名私钥仅在权限受限的仓库外目录，不能入 Git。不得复用旧 approval、旧 Runtime epoch 或直接 INSERT 假安装。若正式审批/镜像/配置来源无法建立，只显示明确禁入，不声称可用。
5. 仅当新实例安装/签名/权限/Runtime 与 zero-worker 启动门独立读回后，启动新 API 预览；核 8080/8434/18181 和第二 Host，做健康、目录、八页及关键交互的浏览器验收。不能为了页面可点而关闭签名、权限、预算或审批门。原隔离预览可保留；端口切换只针对已核 PID，不删除进程外资源。
6. 专项与累计回归、方案代码一致性和无删除检查；verification 落盘，m1 精确提交，更新 D-waves/AOS/Prime。未能全绿则保留现有服务与新数据、写明唯一下一合法步，不把计划当完成。后续回到 P2g30b RETURN Action 正向 producer。

## 停止条件

任何未知提交、需读商城源、需重放旧 12 Run、需手工 `run_definition`、需删除任何对象、缺当前授权/可信签名/独立批准，均在相应动作前停下并转做可独立完成的构建或首链代码。旧卷历史不作为本波任务。
