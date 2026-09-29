# W5CB4 BG-00bq｜网络激活只读预览产品入口 verification

## 方案与范围

AGENTS.md、aos-engineering-delivery、231/231-5/231-9、41 网络方案及 BG-00bp 复习；方案 `b6e424c4`，实现 `22588266`。当前权威库只读：`NetworkPolicyRevision` ObjectType=0、正式 ActionType=0，正租户 meta_membership 仅1条 owner，尚无独立 checker。按长程机制把正式激活留在禁入，本波做独立产品入口，不注册动作或写策略。

## RED/GREEN、自测与方案一致性

- RED：初次 Vitest 退出127，因工具会话 PATH 缺 node；改用当前 Web 实际运行的 bundled Node。新测试因面板模块缺失退出1。此后没有改依赖锁文件。
- GREEN：Network 预览/Egress/Data/ModelRuntimePage/安装候选五组 `25 passed`，退出0；`pnpm --dir apps/web exec tsc -p tsconfig.json --noEmit` 退出0，`git diff --cached --check` 退出0。
- UI 构造只产生 HTTPS/443、固定明确选择主机、无公网回退的 active *候选*；要求精确 Egress id/revision/hash、预计 head、有效期。唯一动作是调用 BG-00bp 只读预览，当前身份/租户/auth revision 前后不一致时不接受响应。响应必须显式 `activationAllowed=false` 且含正式 Producer/原子消费者 blocker；页面只显示阻断、无发布/批准/运行按钮。文本 approvalRef 标明不构成批准。
- Web dev server 8434 `/aip/model-runtime`=200；新 TSX 模块=200/45244 bytes，转换输出含“只读预览阻断项”“不构成批准”；18181 无监听。browser-pilot 不可用，本波无截图交互验收；HTTP/模块与组件测试不证明真实业务配置完成。

## 权威与剩余风险

真实库 `aos_current_preview_20260927@a0v_115` 及卷 `aos-a0v-recovery-pg-data` 保持只读；BG-00bp 复核 ActionType/Network/binding=0，UI 波无数据库写。预览是快照，前端校验只为易用性，未来正式 Producer/审批/同事务消费必须由服务端重核时间、租户、成员、maker/checker、当前 head、依赖与一次性 Receipt。当前出站 active0，网络策略正式入口不可用；八配置、Owner/Host、自然首链、卸载重装/观察 pending。下一波 BG-00br 对受控 ActionType/ObjectType 元数据与合法 checker 身份做方案/隔离试验，不能在当前库造元数据或用假账号冒充验收。
