# W5CB4 当前源码候选构建核验（2026-09-27）

## 边界与结论

- 依据 `w5cb4-current-code-fresh-preview-plan-20260927.md`，本子波只完成最新源码候选的安全构建，**不是**签名、Registry 发布、安装、Runtime 启用或八页业务验收。
- 起点 `m1@4524c369`。原 `aos_meta_head` 为 `a0v_092`，原 Runtime 权威未知/禁入；继续不迁移原库、不重放旧 12 Run、不手工 `run_definition`、不读商城源、不启自然 worker/Provider。
- 当前隔离全栈预览的 8080 API 与 8434 Web 各返回 HTTP 200；8080 仍接已迁移的保留克隆，18181 无监听。浏览器目录此前返回 `400 MANIFEST_INVALID`，本子波未宣称修复该页面。

## 实施与实证

1. 当前构建 profile 精确指向 core `1.4.0`、Niushop `1.23.0`、growth `1.11.0`、operations-base `1.2.0`；源码前置检查读出 4 Bundle、3 Runtime 成员、8 模块、15 操作。旧 profile 不变，漂移时报错。
2. Builder 增显式 `--retain-artifacts`：本次运行保留独立输出及中间物；旧默认清理语义不变。测试基础夹具增显式 `AOS_TEST_RETAIN_DATABASE=1`，在此模式保留隔离测试库；常规模式不变。早先 RED 曾触发项目自动测试库清理，用户已明确准许这类测试夹具行为，但此后专项均用保留模式。
3. `AOS_TEST_RETAIN_DATABASE=1 uv run pytest -q tests/extension_runtime/test_build_ecommerce_current_candidates.py --disable-warnings --tb=short`：`3 passed, 7 warnings`。修改脚本编译检查与 `git diff --check` 通过。
4. 在新建且保留的 `/Users/ddt/work/projects/ai_agent/.aos-current-build-BsJyrJ1r` 执行当前 profile 的 `--build --retain-artifacts`：退出码 0，Receipt `outcome=BUILD_GREEN`，`outputTreeHash=sha256:41bc21507900f41b224c696354217412ba529e3c280d0c1a8f2845ff2730b2aa`，Receipt 文件 SHA256 `9ca926aa93109c7e9d9f1d246fac82ec354ea4f0513f4e836d185564a64fb6cc`。三张镜像具有 exact digest；Receipt 中 Registry 发布、安装变更、Provider 调用、外部发布计数均为 0。

## 方案/代码复审与风险

- 对照产品首链和技术安装边界，本波只推进可重复的当前源码构建，不把镜像存在或 HTTP 200 当作真实业务链完成。签名、信任根、正式 Registry/Installation、Runtime 权威与浏览器验收仍缺；旧 `bundle://a0v-canonical/...` 不能沿用。
- 保留模式覆盖构建输出和工作目录及 helper 镜像/容器；当前 helper 已停止并保留。未运行 `qualify`，因此没有资格验收结论。构建 Receipt 中 `gitHead` 是起点 `4524c369`；本子波提交后须由后续波重新校验源码/产物绑定，不借 Receipt 直接发布。
- 原 `aos_meta_head` 未迁移；8080 仅隔离克隆预览，不能称作当前生产实例。未删除业务卷、库、备份或其他历史资源。

## 下一波

先按上位方案细化“当前源码候选的持久信任根、签名和全新隔离安装”文件级方案；用正式 API/控制面逐门验收，再切换 8080 预览并在浏览器核目录与八页。若签名/审批/安装权威无法独立建立，保持禁入，转做可独立完成的首链代码，不降低校验。
