# SC4-5l6h 当前代际电商领域包构建、签名与重装方案

日期：2026-09-15
代码基线：`b3a5c943`
任务权威：`A0V-CURRENT-ECOMMERCE-PACKAGE-REINSTALL-20260915`，owner=`m1`，有效至 2026-09-17 23:59 +08:00。

## 与长程业务目标的关系

本波不是为了让页面或测试单独变绿。主库已经具备 ProductEvent、DataRequirement Outbox、十二源 Snapshot、分析恢复及完成 Receipt，但实际安装仍指向 Niushop 1.5 / growth 1.7，且当前 generation 已围栏、资源已释放。只有把已冻结的 Niushop 1.22 与 growth 1.8 作为真实可验证、可安装的签名领域组合，经安装、配置、禁入、恢复、卸载和重装演练，下一波栖月汇真实数据自然触发首链才有可信的包与运行边界。

## 当前事实与版本决定

- 当前仓库候选坐标为 core 1.3.0、growth 1.8.0、Niushop 1.22.0、operations-base 1.2.0。growth 1.8 增加签名前端与 `analyst_workspace_view_v1`，历史提交 `1b03336c` 已完成实际 OCI registration、2048 heartbeat、读取 probe 和 cleanup；其候选目录从该提交到当前 HEAD 逐字节未变。
- Niushop 1.22 由 1.21 的冻结树追加 `snapshot-readiness.v1.json` 并更新版本/eval，提交 `1810c18a`；已完成候选静态合同，但没有实际 build/sign/install。1.22 包含十二源映射、字段/关系质量、business cohort、facts 与 readiness 策略。
- 现有 `build_ecommerce_ui_candidates.py` 固定 growth 1.8 + Niushop 1.5；`build_niushop_snapshot_candidates.py` 仍只固定早期 1.4。原通用 builder 固定 growth 1.7 + Niushop 1.3。不得临时 monkeypatch 命令或改通用默认值。
- 现有永久签名后继根 `growth-ui-1.8-registry/signed-bundles-growth-ui-1.8` 有14个版本：core 1.1–1.3、Niushop 1.1–1.5、growth 1.4–1.8、operations-base 1.2。新根只追加 Niushop 1.22，预期15个版本；旧根不改写，中间1.6–1.21候选不必伪装成已发布版本。
- 当前精确前驱安装为 `97aeb2e7-59ba-40f6-89a3-fb0293bc0497` active@5，lock `sha256:a4441a4383783cb2a2f32171c52eb2718f526a5f56102dc5c0e12bf79299a42b`，overlay `a0v-canonical-ecommerce-v1`；generation `3a445eee-aa28-4459-9e5a-f12a806a94b` 在本次开机后为 `enabled=false / fenced=true / desired=enabled / observed=unknown`、revision5/epoch4，三项资源 released。它是安全禁入状态，但尚不满足 replacement guard 对当前 `disabled_committed` 的精确要求，不能仅凭资源释放把它写成 drained predecessor。

## Rules、主路径与停止条件

1. 固定单主路径：候选合同 → 隔离构建/资格审查 → 永久签名后继根 → 第一次安装控制演练 → 卸载 → 第二次重装 → 最终 Host 连续性。所有写操作走既有 Registry、Installation、Runtime、Configuration、Disable、Uninstall Owner，不直接改安装表、binding、lease、dispatch 或 Receipt。
2. build 输出、OCI journal、签名根、备份和命令 intent 只写 `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/current-ecommerce-package/`，目录0700，身份/命令/证明0600。已有目标、intent 或结果时停止并只读观察，未知结果不重发。
3. 隔离 Runtime 只用 `colima-aos-extension`、linux/arm64、userns、seccomp、无宿主目录挂载。资格审查要求三成员 exact registration、2048 heartbeat、released cleanup、growth 只读 fixture probe，以及 image index、digest、dependency lock、SBOM、backend、schema compatibility/requirements 的篡改拒绝。
4. 永久签名复用既有 Ed25519 信任根但绝不输出私钥。逐字节验证旧14版本，验证本次 build/qualification 的 gitHead、树 hash、成员、贡献数与运行 admission；新根只增加 Niushop 1.22，growth 1.8 必须与旧根字节一致。签名前后不发布外部 Registry、不改项目 `.env`，API/Host 使用显式新根。
5. 第一次安装 A 以97a active@5为精确前驱，组合必须唯一解析到 core1.3/Niushop1.22/growth1.8/operations1.2。按 maker/checker 职责分离完成 draft→submit→approve，再由 runtime Owner prepare→verify；配置继续使用当前四类正式 Source 引用并重新计算配置 revision/hash，不复制旧 installation 的授权 Receipt。
6. enable A 前要求主库050、正租户九路 dispatch、canary零、Source/Provider/预算/审批当前门禁、唯一 Host。enable 后启动 Host，只允许当前 A generation；观察 ready/enabled/unfenced、三容器和租约续期。异常或同阶段失败两次立即停写并保留诊断。
7. 控制演练对 A 执行 disable/fence，要求 schedule/Run 排空、generation exact、全部资源 released、旧路由不再可调度。系统级重启只停止并重启已核实的唯一 Host，不重启 API/数据库；确认围栏保持，再经新的 current enable Receipt 恢复 A，禁止复用旧授权。
8. uninstall A 必须由 Uninstall Owner 检查 fenced/drained/released，保留不可变历史与 Receipt。随后创建安装 B，使用同一15版本签名根完成 approve/prepare/verify/configure/enable；B 成为最终可用安装，A 不得复活或持有运行资源。
9. 每一步都核正租户 `org-org/dev-project` 与 canary `dev-org/dev-project`。canary 全程零安装、零路由、零业务交付；不读取或写入 canary。上游商城只读和真实经营动作留到下一波，不把 build/install 结果写成真实首链成功。
10. 不 push；230 L0 挂起；不触碰用户已有 `overall-progress-20260913.md`、`package.json`、`package-lock.json` 差异。失败不 reset/rebase/clean，不对主库做破坏性降级。

## 实施文件

- 新增 `scripts/build_ecommerce_current_candidates.py`：严格组合既有 profile，只选择 core1.3/Niushop1.22/growth1.8/operations1.2；复用 growth OCI 只读 probe，预期13个 runtime operation、八模块/八路由。
- 新增 `services/aos-api/tests/extension_runtime/test_build_ecommerce_current_candidates.py`：验证原 builder 不变、两个精确替换、候选目录/操作数、growth fixture 与版本漂移拒绝。
- 新增 `scripts/a0v_ecommerce_current_signed_successor.py`：复用既有永久签名 helper，以 growth1.8签名根为14版本父树，仅追加已资格审查的Niushop1.22，生成15版本不可变新根。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_current_signed_successor.py`：验证父树/新树、版本集合、growth字节继承、运行 session/admission 和篡改拒绝合同。
- 新增 `scripts/a0v_ecommerce_current_reinstall.py`：`observe / create-a / prepare-a / verify-a / configure-a / enable-a / disable-a / recover-a / uninstall-a / create-b / prepare-b / verify-b / configure-b / enable-b` 固定状态机；每个命令先写 intent，结果未知时仅 observe。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_current_reinstall.py`：验证精确 predecessor、阶段/etag/generation、幂等 key、权限分离、排空/资源释放、uninstall 与 B 不复活 A、canary拒绝。
- 新增本波验证文档 `sc4-5l6h-current-domain-package-reinstall-verification.md`，并把构建、资格、签名、安装、配置、Runtime、停用、恢复、卸载、重装与 canary 证据逐项落盘。

## preHash

- `scripts/build_ecommerce_runtime_candidates.py`：`c6261fdea9d5398b3ccb900434f7effb8d1f69ad29c1455792ae64b70172ede5`
- `scripts/build_ecommerce_ui_candidates.py`：`520bab0f333c7b617b9ae65adfc20762ce1a32a6fec1b22abd624070d3547d58`
- `scripts/build_niushop_snapshot_candidates.py`：`6e784d50b2b4776e3e2e571098431b378656509031f1abe23b4fe2b1c80c11ee`
- `scripts/a0v_ecommerce_ui_signed_successor.py`：`6179acdb403e24893878dcad1de8feaf39ef8596625457ef7e7864a8a7ecba48`
- `scripts/a0v_qyh_reboot_recovery.py`：`ac930ffb57c527cb442b45bcdd7d5658081940462370998e2140ea2f1d5e4d39`
- growth 1.8 manifest：`75efe478e04d3b9d9691e1a9e5522d58b5b2e27cfcdc8af6ef367c34842e2c53`
- Niushop 1.22 manifest：`d194249c902713ab2b047d7a8abec66a17a8c767d234b1cd8d304aa83a574960`
- 三个新增脚本、三个测试与验证文档：`NEW`。

## 本波六步退出条件

1. 版本与源码盘点完成，旧签名根/当前安装/主库050事实可重放。
2. 本方案提交，新增范围、preHash、停止条件和双安装最终态明确。
3. 三个脚本及合同测试提交，原通用 builder、历史候选和签名根未修改。
4. 当前四包隔离 build/qualification 与15版本永久签名后继根通过，外部发布和安装副作用为零。
5. 安装A完整完成 enable→disable/fence→Host重启保持→重新授权恢复→uninstall；所有动作有实际 Receipt，资源释放且 canary 为零。
6. 安装B完成重装、配置、enable 与唯一 Host 连续性；API/5173/8434健康，主库与业务基线无越权漂移。落证据提交后进入下一波栖月汇真实 Source/经营计划/自然 ProductEvent 首链，不形成发布结论。

## 实测后的窄化修订

2026-09-15 安装 A 的 configure 已由唯一 Host 成功提交；第一次 enable Receipt `7df3448d-b526-4a83-8bab-a9d4e9892fa6` 被接受后，replacement guard 读取前驱发现其 `desired=enabled` 且缺少当前 revision5/epoch4 对应的 `disabled_committed`，因此 Host 以 `RuntimeConflict` 安全停止。A 保持 disabled/fenced，enable Receipt 仍为 accepted，没有业务调用或 canary 写入。

在继续启用 A 前，控制器新增 `drain-predecessor`：只接受上述精确前驱、generation、revision5/epoch4、disabled/fenced/desired-enabled/unknown、三资源 released、全部历史 operation 终态及 canary 零；通过原 RuntimeDisableService 创建新的 disable Receipt，再由原 RuntimeDisableConsumer 单次消费并核对同一 operationId 已 succeeded。这样先生成 replacement guard 所需的当前不可变排空证据，再重启唯一 Host 续办既有 A enable Receipt；不得重发 enable，也不得直接更新 binding/event/outbox。

A 完成停用、Host 重启与 `recover-a` 后还需第二次正式停用才能卸载，因此控制器同时增加 `disable-a-final`，复用同一阶段校验但使用独立 intent 和幂等键。原 `disable-a` 的命令文件、键和行为保持不变。
