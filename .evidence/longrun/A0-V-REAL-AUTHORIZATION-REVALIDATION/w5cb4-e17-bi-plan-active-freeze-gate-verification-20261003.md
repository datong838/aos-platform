# W5CB4 E17｜签名 BI Plan 受控冻结门禁验证

## 实施与 RED

- 上位 231-3、551 与文件级 `w5cb4-e17-bi-plan-active-freeze-plan-20261003.md` 已复习。普通 Plan freeze 原语改为调用方持有事务入口，原普通 operation/hash/行为保留；新增内部 `SignedBIPlanActiveFreezeService` 严格串行核正式 OIDC actor、当前持久权限、active 安装/强 ETag、签名 Registry/模板、原 rebind 与 prepare Receipt、Plan draft exact hash/version，再沿用原 Store readiness gate。若可冻结，同事务才会核当前 frozen 配置角色 reader 与签名源后提交。
- 原 Growth1.13 签名安装全链新增冻结调用先 RED：`ImportError: SignedBIPlanActiveFreezeService`，exit 1；补最小内部服务后走到原 Store readiness，六个职责均报 `SKILL_BINDING_NOT_ACTIVE`。原链没有正式发布/active 的 SkillBinding，这是独立的真实来源依赖，不得用手插行或 mock 绕过。
- 因上述依赖，本波收口为内部失败封闭门禁；公开 POST/GET、冻结 Receipt 正向回读及当前配置源正向证明延至原 Skill 发布/绑定来源齐备后。代码不能被报告为“Plan 已冻结”。

## 证据

- Growth1.13 原 signed Registry→安装→OCI→runtime apply/verify→active→重绑定→尝试冻结：`1 passed, 7 warnings`，exit 0；断言原 Store `SKILL_BINDING_NOT_ACTIVE`、Plan head 仍是重绑定 draft revision、`bi_responsibility_plan.freeze` Receipt 数为 0。错 rebind key、安装 ETag、空 trust、dev actor、跨租户均拒绝。Growth1.12 同链 `1 passed, 7 warnings`，exit 0。
- BI/Plan/Stage 相邻十文件：`119 passed, 8 warnings in 44.54s`，exit 0。`py_compile`、精确 `git diff --check` exit 0。原普通 freeze 的相邻测试保留。
- 真实当前库 `aos_current_preview_20260927@a0v_135` 全程只读；隔离 PG 库 `aos_test_*_ti4_test` 的六实例是测试前置，不是当前正式生产者。此前浏览器 `org-org/dev-project` 显示 37 仅评测/0 发布、三阻断、按钮 disabled、无电商入口，Host 18181 关闭。

## 风险与下一入口

内部冻结正向代码路径尚无完整原 Skill 发布/绑定生产者证明，不开放 HTTP。下一波先沿原 `AipSkillRegistry.create_binding` 追 published Skill、CapabilityBinding、预算/审批及 active 绑定来源，形成隔离原链正向与负向；再继续冻结、只读 Receipt 与配置 reader。当前正式 OIDC/三身份、Growth1.13 正式签发、八配置与 Host Owner 依然缺失，首链未完成。长期 Goal 继续 active。
