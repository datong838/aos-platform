# W5c1 Direct Successor 仅批准创建验证（2026-09-24）

## 结论

**GREEN，但只到 approved。** 新 installation `ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc` 为 approved/etag3，composition `1d6cd2f0-e8c5-4f95-bba2-2603c15b7426`，lock `sha256:90de41222929fb40a52a33f7222b818a4d3a94c92a6b07251e8a6825d41783e4`；四包版本 core 1.4.2、niushop 1.23.2、growth 1.10.2、operations 1.2.2，8 个工作台模块。其 runtime binding/operation/resource 均为空，尚无 PreparedJob、未启用。

## 过程与独立回读

- 按 W5c1 方案 `3bbf1a35`，只读预检 DS active/etag5、binding rev13/epoch7 disabled/fenced、三资源 released、全 operation 终态、九路 9/9 legacy/fenced/group rev365、claim gate0、12 schedules disabled、active attempt/canary0；正式 detach 权威为 W5b0 operation `a71ece36-0abd-486e-972e-8bf69628d2ca` 的 detach Receipt hash `sha256:85f803080a8d348da90040540c5cc1d3fef48bbee857db3598265eaf0a37dd9c`。W5b1R3 新 disable 是 no-op dependent，不能冒充 detach Receipt；初版只读预检因混淆这两个 operation 拒绝，未写 intent/安装，修正后预检通过。
- 私有 intent/result 为 O_EXCL/0600，前缀 `a0v-w5c1-ds-successor-20260924-v1` 之前 Command 数0。只调用一次原 `create_approved_first_installation`，取得 composition/create/submit/approve 四个正式 Command；返回状态 approved/etag3，非 replay。
- 独立数据库回读新 head、锁 payload `currentInstallationRef` 精确指向 DS ID/revision5/lock/overlay、四个包版本、四 Command、8 模块；原 DS 仍 active/binding rev13，九路 9/9 legacy、12 schedules off、active attempts0、canary0。未备份/读取商城源表，未启动 Runtime Host、未产生业务 Run。
- 定向测试 2 passed，`git diff --check` 通过。方案规定的“只批准、不激活、不切流”与结果一致。

## 下一波 W5c2

先方案，精确核验新 approved 与 DS 的旧 detach/资源/attempt/definition 权威，再经原 RuntimeUninstallGuard 正式卸载 DS。随后仅在唯一独立 Host 持续存活的前提下，逐阶段 prepare/verify 新安装，必须由原 Host 生成真实 PreparedJob；任一 Host 中断/结果未知先冻结并走正式 preparation-reset/direct successor，不复活已释放资源。12 条旧 selection/control 和调度继续关闭。
