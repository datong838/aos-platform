# W5CB4 BG00dm｜growth 1.12 独立克隆不可变 successor 验证

## 上位、范围和 RED

复习 231 主计划、231-2/231-3、BG00dl 恢复证明及 Registry/Composition/Installation 既有服务。源为 `colima-aos-extension/aos-a0v-recovery-pg` 当前命名卷，只读；唯一写目标为 `colima-aos-a0v-test-only/aos-bg00dl-isolated-pg` 新卷，回环18440。旧安装 approved@3/active NULL 不满足活动 `currentInstallationRef`，因此只新建独立克隆候选，不伪造原位升级。测试先于新脚本运行：`services/aos-api/.venv/bin/python -m pytest -q .../test_growth_112_successor_clone.py --disable-warnings` 退出1，9个 `FileNotFoundError`（入口未实现）；最小实现后 10 passed。

## 证据表

| 检查 | 命令/目标 | 退出码与结果 |
| --- | --- | --- |
| 目标/签名/基线只读预检 | `services/aos-api/.venv/bin/python scripts/a0v_growth_112_successor_clone.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-growth-112-signing-receipt-r3-20260930.json` | 0；test-only context/容器/独立卷/回环18440、a0v_118、BG00dl 17 表全摘要、旧 growth 1.11 hash吻合；1.12 signed tree `sha256:48a89116…fdada`、根修订 `sha256:88b57e1d…3701e` 可核；effects0 |
| 当前签名独立回读 | `check_signed_receipt(.aos-current-build-pyGkqQ/signing-receipt.json, expected_growth='1.11.0')` | 0；旧根 `sha256:0a99db8b…95752` 和四包签名可核。两根仅在克隆私有文件合并 |
| 错 context | 同预检加 `--context colima-aos-extension` | 2；`SAFE_BLOCKED/CLONE_TARGET_DRIFT`，进入 DB 前拒绝 |
| 旧 receipt 冒充新 | 以当前旧 `signing-receipt.json` 作 `--signed-receipt` | 2；`SAFE_BLOCKED/SIGNING_RECEIPT_DRIFT`，进入 DB 前拒绝 |
| 克隆演练 | 上述新旧两 receipt 加 `--apply-clone --state-dir /Users/ddt/work/projects/ai_agent/.aos-bg00dm-successor-state-20260930` | 0；新 growth 1.12 published、独立 composition/安装 `42785d78-5914-4a54-a078-e5d2c7f48481` approved@3/active NULL；八工作台、四包、三依赖边；本地 maker/checker 字符串不同，仅 test-only |
| 克隆预写备份 | `pre-successor.dump` | 3,951,403字节，SHA256 `63228d9f99dc6d6e4f6dc9be9870ca999ba04d0ca742b4b83909a678029d7838`；`docker ... exec -i ... pg_restore --list < dump` 5621行；状态目录0700/文件0600 |
| 克隆后只读 | `psql -U bg00dl_admin -d aos_current_preview_20260927` 在 test-only 容器 | Registry5、lock2、安装2；旧和新安装均 org-org/dev-project approved@3/active NULL；operation/binding/Host identity/assignment/config 0；dev-org 安装0；旧 Registry/lock/安装全行旧集合在新集合中不变 |
| 当前源未动 | 当前容器固定17表 count+全行摘要与 BG00dl `source-clone-digests.json` 比较 | 0；17/17一致；Registry4/lock1/安装1，运行控制均0 |
| 专项及相邻回归 | 10 新测 + current registry/install、1.12 signer、signed lifecycle PG | `18 passed, 1 skipped`，退出0；`py_compile`/`git diff --check`退出0 |

第一次 TOC 复查漏传 `docker exec -i`，容器读到空 stdin 并报输入不足；改为带 `-i` 的命令后 5621 行。此失败只在备份文件的只读复查命令，未影响克隆写入或结果。演练没有使用商城源、旧12 Run、手工 run_definition、Host、worker、Provider或外部发布。

## 方案/代码复审与结论边界

新增 `scripts/a0v_growth_112_successor_clone.py` 只接受精确 test-only context/容器/卷/端口/租户，默认只读；写入需显式开关、新状态目录和两份各自有效签名，先保存意图和克隆预写备份。复用已有 Registry 服务和首装 helper 的通用 Composition/Installation 服务调用；没有复用固定 a0v_107 空库入口，也没有改现有业务代码。旧对象逐行集合与新对象分离，成功后只读检查 Registry5/lock2/安装2和零运行控制；状态目录存在或克隆基线漂移时不得直接重发。

**GREEN 范围仅是独立克隆中的不可变 successor 与批准状态机机制。** 新 1.12 的签名为本地开发 key；测试 maker/checker 不是当前正式组织身份。当前 trust-root 正式批准/轮换、三身份/Owner、八配置、当前库零执行切换、恢复/卸载重装与自然首链均未证，不得启 Host 或把这次 clone 算作真实经营闭环。下波 BG00dn 先只读查正式签发者、组织独立 checker 与三身份来源，并在缺源时做可独立完成的 fail-closed 代码，不迁当前库。
