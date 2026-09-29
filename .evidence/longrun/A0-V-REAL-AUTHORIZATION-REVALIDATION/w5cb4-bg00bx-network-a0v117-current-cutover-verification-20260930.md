# W5CB4 BG00bx｜当前权威卷 a0v117 安全切换验证

## 输入与执行

上位 231/231-3/231-5、BG00bw 代码 `49ffc96e` 和本波文件级方案。开始时 m1 单写者，用户浏览器插件与 pnpm lock 未提交改动保留。当前唯一卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_116`、正租户批准安装1、dev-org安装0、binding0；Host/worker/Provider关闭。

1. Web LaunchAgent bootout、API SIGINT 后，`lsof` 8080/8434/18181 退出1（无监听）；当前库非 idle 其它会话0。PG保持可访问。停机一致备份 `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260930-bg00bx-Iny8lH/aos_current_preview_20260927_a0v116.dump`，3,953,550 bytes、mode600、SHA256 `4fa33a511d28883f40a4fcff467eabb0d4397df6b88d3d09d3e634a027de19b0`；容器 `pg_restore -l` 退出0。
2. 全库恢复至新 `aos_bg00bx_cutover_testonly_20260930`，`--no-owner --single-transaction --exit-on-error` 退出0。源/克隆 a0v116 安装五控制表 count/row digest 一致；克隆升级117退出0，固定两条元数据与 Producer合同相等、a0v115/116/117触发器启用、runtime修改固定ObjectType 42501、普通对象 INSERT 成功后回滚、直接 active revision INSERT 23514 后回滚。
3. 再次 `lsof` 无执行端口、源116/固定行0/其它活跃会话0、卷名与备份SHA一致，当前库 Alembic 精确116→117退出0；版本117、固定ObjectType/ActionType各1、三触发器启用、网络正式Proposal/ApprovalEvent/head/revision与binding0。迁移后源/克隆五控制表仍逐项相等：`bundle_installation 1/4398438098674159491`、`bundle_installation_revision 3/1650834216456423558`、`asset_bundle 4/1695185680822825726`、`asset_bundle_version 4/-790554283954760494`、`extension_runtime_binding 0/0`。
4. `scripts/a0v_current_preview_http.py` 与其精确测试预期头更新117。`docker restart aos-a0v-recovery-pg` 退出0，卷仍 `aos-a0v-recovery-pg-data`。签名 Receipt preflight `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：approved安装、published4、binding0、版本117。API/Web启动后 18435/8080/8434 LISTEN，18181无；API health/ready/OpenAPI 200；八工作台和 `/aip/skill-publish`、`/aip/agent-catalog` 逐页200。第一次逐页请求设置5秒时遇 Vite 预热超时，后续20秒重测10/10均200；不把 HTTP200 当业务验收。
5. `test_a0v_current_preview_http.py` 加网络相邻专项17 passed/1 skipped，`compileall` 和目标文件 `git diff --check` 退出0。browser-pilot 本会话不可用，未取得交互截图；页面与按钮的浏览器证据待工具恢复后补。

## 结论与下一波

当前最新命名卷与 m1 代码一致，元数据来源已由静态迁移注册，运行角色不能改固定ID；a0v116 active DB门继续拒绝直接写。真实第二 checker/OIDC、八配置候选、Host assignment/Owner、ApprovalEvent原子消费与自然首链仍未齐备，Host继续禁入。下一波 BG00by 只读审 ApprovalEvent 当前状态/版本/撤销/消费权威，再选独立最小代码切片；不能造账号、高权限捷径或直接开 active。
