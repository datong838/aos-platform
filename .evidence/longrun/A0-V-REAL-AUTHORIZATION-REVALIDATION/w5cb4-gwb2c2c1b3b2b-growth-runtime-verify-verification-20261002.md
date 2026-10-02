# GW-b-2c2c1b3b2b 原 Growth 准备与验证联测

2026-10-02 09:10 CST，基线 `AOS-001115` / `aos-platform/m1 74af70f7`。先复习 231-3 第3/6节、231-5 第9节，原 RuntimeLifecycleService、PreparationWorker、CurrentSchemaConditions、CurrentControlPermission、原签名 Growth 1.12 Registry/Composition/Installation。文件级方案在 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md` c1b3b2b 节。仅 disposable 完整 `a0v_135` PG 与 `colima-aos-extension` 的隔离 OCI，本地 r3 开发签名；当前真实库未写。

新测试沿同一原 Registry/Composition/Installation approved@3 来源：无 schema receipt 时原 CurrentSchemaConditions 以 `required schema migration is not installed` 拒；经前切片原物理 schema 检验及 maintenance `apply_once` 后，test-only 持久 membership 的 `test-author` 经原 RuntimeLifecycleService 请求 runtime-apply；原 PreparationWorker 使用持久化 Registry 当前 record、签名原字节、当前条件与权限读者、缓存精确镜像，`prepared()` 返回 applied/无 active；原 runtime-verify 请求和 `job.verify()` 后安装 active、binding `ready/disabled/fenced`，dispatch 零、dev-org 安装零。`job.stop()` 后 owner 容器集合回到基线。`preparation_admission=lambda:True` 仅为隔离测试 Host seam，不是当前正式 Host assignment；测试 membership 不是独立 API/OIDC 身份。

相邻 RED：新增 Growth 测试在同一 session PG 先留下合法 disabled binding，原 `signed_installation_case.py` 用无 scope/installation WHERE 的 binding first-row 断言读错对象，65项中1 failed。仅把该 helper 的 binding 查询和资源 lease 断言限定为自身 `scope`、`draft.installation_id` / resourceId；不改产品代码或重排测试。随后同顺序 65 passed、7 warnings、退出0；逆序两文件 2 passed、退出0。新增 dispatch/dev-org 断言后专项 1 passed、退出0。`py_compile`/`git diff --check` 退出0；隔离 OCI owner 容器零残留，源库只读版本仍118。

结论限于历史 1.12 本地签名包的隔离 runtime-apply/verify 基础设施。1.12 backend 与今日 accepted-stage 代码有4处不同和1个新文件；本测试没有正式当前信任根、独立 API/Host 身份、八类当前配置、首登记/正式 cutover 或自然 Occurrence、Analysis/Stage、首条经营闭环。当前实例今日最新版本完整重启仍 SAFE_BLOCKED；Host/worker/Provider 不开启。下一波应核今日 backend 的新不可变 signed successor 与八类配置候选/正式 Owner，不能用此 active test installation 冒充正式业务安装。
