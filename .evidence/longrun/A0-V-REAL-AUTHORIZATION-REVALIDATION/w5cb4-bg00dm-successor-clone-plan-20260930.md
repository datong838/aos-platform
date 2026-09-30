# W5CB4 BG00dm｜growth 1.12 独立克隆不可变 successor 方案

## 上位与当前事实

复习 231 主计划、231-2 的已签名精确 release/不可变 digest 与 231-3 的 composition/安装状态机、maker/checker、CAS/Receipt。BG00dl 的 a0v_118 新备份在独立 PG16 克隆完整恢复且 17 张控制表摘要一致。当前真库只读；旧安装 approved@3/active NULL、旧 lock growth 1.11.0、Registry 四个 published。新 1.12.0 的四包本地隔离 build/qualification/sign GREEN，但开发 key 与当前 trust root 不同，不是当前正式批准。

## 文件级计划与 RED 顺序

1. 只读审 `services/aos-api/aos_api/asset_registry/{registry_service,registry_store,release_policy,composition_service,composition_store,installation_service,installation_store,installation_revalidation}.py`，旧 `scripts/a0v_current_preview_{registry_publish,installation}.py` 仅作历史基线。先冻结克隆数据库身份、旧 17 表摘要、签名 receipt/tree hash/信任根 revision；脚本绝不连接 `colima-aos-extension` 或当前数据库端口。
2. 在 `services/aos-api/tests/extension_runtime/test_growth_112_successor_clone.py` 写 RED：默认只读预检；错 context/卷/库版本、当前实例/错误租户、旧 lock 漂移、签名 receipt/根不匹配、缺批准 authority、maker=checker 均拒绝且零写；成功 clone-only 路径须由真实 Registry/Composition/Installation 服务新建独立 1.12 release、新 lock/installation/Receipt，旧安装与旧四版摘要不变。对未知提交结果只能先只读 Receipt 对账。
3. 最小新增 `scripts/a0v_growth_112_successor_clone.py`，默认 dry-run。仅在显式 `--apply-clone`、精确 `colima-aos-a0v-test-only` 容器/新卷/库的三重身份，且已验证 BG00dl 备份/摘要与 1.12 当前提交签名链后，才使用既有服务写 **克隆**。测试人物/开发 key 在克隆仅证明机制，不视为正式组织 authority。拒绝将旧 lock/安装原位改写；成功应是新的不可变对象和幂等 Receipt。
4. 先 RED 后最小代码；专项 + Registry/Installation 相邻回归；再次比较旧对象与拒绝后的全控制摘要；复核方案/实现/风险，verification 落盘精确提交。当前库写入与正式 trust-root 轮换/三身份/Owner 是之后独立门；Host、worker、Provider保持关闭。无商城源读取、旧 Run 重放、手工 run_definition、230 L0、push。

## 退出判据

BG00dm 的 GREEN 仅代表隔离克隆不可变 successor 机制，需真实 PG 正负证据、签名来源和 Receipt/旧对象对账；正式当前安装、八配置与自然首链仍 pending。任一正向缺合法克隆条件则保留 RED 和拒绝证据，转做独立代码项，不制造当前批准身份。

## 施工前合同复核

`CompositionService.resolve(currentInstallationRef=...)` 会经 `InstallationStore.load_active_baseline_in_transaction` 读取**活动**前驱；当前旧安装为 approved@3 且 active_revision=NULL，不能伪造活动基线。克隆正向只新建独立的 1.12 composition 与安装候选，旧 approved 安装原样保留；真正的替换/切换仍需正式批准与独立窗口。克隆 Registry 快照要同时验证旧 1.11 和新 1.12 签名，两份开发/当前 public trust root 只可在 test-only 内组合使用，不能写入当前信任根或把测试人物认作正式 checker。
