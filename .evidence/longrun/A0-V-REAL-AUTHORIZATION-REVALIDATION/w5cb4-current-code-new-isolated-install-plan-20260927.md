# W5CB4 当前源码新隔离库首装计划（2026-09-27，方案先行）

## 依据与当前边界

- 复习 `a0-v-canonical-ecommerce-first-install-plan.md`、当前源码预览/构建/持久签名三份计划与核验：正式路径必须是 Registry 四包发布 → 无 baseline Composition → maker/checker Installation → Runtime 配置/准备/启用 → 正负租户投影。不能把旧固定 1.1/1.4 版本的首装执行器、历史目录/签名根、HTTP 200 或签名树直接当当前安装。
- `m1@59713a08`，新构建与签名在 `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ`；四包 core 1.4、Niushop 1.23、growth 1.11、operations-base 1.2；build/signing Receipt 已留存。原 `aos_meta_head=a0v_092` 不写；现有 8080 是保留克隆预览且目录仍 `MANIFEST_INVALID`。

## 文件级清单与串行步骤

为保持每段结果可核验，步骤 1–3 的空库/正式迁移先作为结构子波单独 verification/commit；步骤 4–6 继续沿此计划各自收口，结构就绪不得冒称整波首装退出条件达成。

1. 只读预检：精确回读 m1、构建/签名 Receipt、签名树/信任根、Docker/PG 容器与数据库列表、原库及 8080 的身份；确认新数据库名 `aos_current_preview_20260927` 不存在，且无未知 current installation/Host 副作用。输出仅摘要，不打印连接口令/私钥。
2. 先在 `scripts/a0v_current_preview_bootstrap.py` 建立新实例专用的默认只读身份预检、显式一次性迁移和保留的 intent/result；再于后续阶段新增 `scripts/a0v_current_ecommerce_preview_install.py` 及对应专项。每阶段先 exact readback，不重用旧执行器硬编码版本/旧签名目录。任何已有未知阶段只读对账，不重发。
3. 先创建**全新** PG 库并按当前 Alembic 正式链迁到 `a0v_106`；新库/迁移日志保留，不执行 DROP/清理。迁移/签名/版本 drift 则停在该阶段，不触原库。
4. 通过正式 RegistryService 以 creator/validator/publisher 分工发布四个 exact 签名版本；独立读回 content/signature/evidence/snapshot。只有一致后才通过 CompositionService 解析四节点三边/八 UI 模块，InstallationService maker 创建/提交、checker 精确批准。`dev-org/dev-project` 仅零 canary。
5. Runtime 三成员准备前先核当前责任/策略/配置/预算等权威；不具备则安装保持 approved/blocked、Runtime operation/binding/Host=0。具备时经正式 RuntimeLifecycle 完成 apply/verify/configure/enable，再零 worker HTTP 预览；第二 Host=0，18181 无监听。
6. 浏览器验收 8080/8434 目录、八页及关键交互的实际渲染和权限禁入；正向租户可见、负向租户 404/空。专项/累计回归与代码方案一致性复审，verification 落盘、m1 精确提交、D-waves/AOS/Prime 更新。前一阶段未核验通过不得进入后一阶段。

## 停止与退出

- 新库已存在但来源未知、当前签名/Receipt/源码不一致、需要覆盖/删除资源、需迁移原库、需读商城源、需旧 12 Run replay、需手工 `run_definition`、审批/签名/Runtime 权威缺失，均保持 fail closed。旧构建和失败签名现场保留。
- 本波只有正式独立读回四发布版本、一 approved/active installation、三 Runtime binding、八正向 UI 与负向隔离、零未知效果、浏览器真验收全部齐全才称“当前预览可用”；否则证据写到已到达的门，下一波针对实际缺口，不造绿。
