# W5CB4 E12 验证：当前 SourceSelection 只读诊断（2026-09-28）

## 结论

本波补上产品准入中的“安装 approved 不等于 active、运行绑定尚未建立”诊断；**没有**生成正式 SourceSelection draft/审批、没有启 Host/worker 或连接商城源。现场唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 的当前 revision 3 仍为 approved、active_revision 空；授权来源/正式管道/绑定/Selection 均为 0。E11 编译器在当前卷不可合法使用，故按 E12 计划的现场收窄条款复用 E10 同一 repeatable-read/tenant-scoped 只读事务，绝不猜选安装或运行绑定。

## 9 步证据

1. 复习 231/231-9、栖月汇产品合同、E09–E11 证据及当前安装表、`RuntimeViewReader`、原 Owner；确认当前缺独立 runtime 身份和 active 安装，不能给网页草案。
2. 计划先行提交 `3dee6fbc`，现场收窄修订 `86c0c15c`、最小文件清单修订 `f0e448f2`。只改 `data_os_store.py`、`PipelineAdmissionPanel.tsx` 及其两侧专项测试；原路由、Owner、运行/签名/源读取均不改。
3. E10 read-only 同一 scoped 连接补最多 2 条安装和绑定诊断；0/多安装、approved 非 active、无绑定、多绑定、无配置均显式阻断。唯一安装 ID 只作非敏感定位，`ready` 仍固定 false，不输出凭证、图节点或可 POST 草案。前端只展示阻断及恢复说明。
4. 专项后端 9/9、前端 3/3；租户 SQL 均含 org/project，安装多解/旧状态/无绑定等负例继续 fail closed。
5. 邻接累计后端 149/149；前端 307 文件、2688/2688；TypeScript 与 Vite 生产构建通过。`git diff --check` 通过。旧 `test_pipeline_registration_truth.py` 两项因遗留 shell allowlist 目录缺失的独立环境错误未计为绿；未为它恢复旧历史目录。
6. 浏览器 `/data/pipelines/P01-shop-qyh` 经最新 API 加载与重启后复验，明确同时显示“这条管道尚未完成正式登记”“安装尚未激活；已批准不等于可运行”；保存禁用，没有审批动作。列表仍 0/0，真实来源 0。
7. 一致性/风险复审：读取只作诊断，未将“唯一安装”认作签名包匹配，未将绑定存在认作配置授权；现有 `EXACT_RUNTIME_REVALIDATION_REQUIRED` 始终保留最终 Owner 门。新读取失败由原 HTTP 503 安全错误路径接住，不泄漏 SQL/凭证。后续若出现多个安装必须让用户选择并由服务端精确核验，不能默认第一条。
8. 用当天最新代码和原命名卷再完整重启：容器 `aos-a0v-recovery-pg` 保持卷 `aos-a0v-recovery-pg-data`，DB `aos_current_preview_20260927` 为 `a0v_109`；8080 `/v1/health` ok、`/v1/ready` ready，8434 HTTP 200 且浏览器内容正确，18181 无监听。API 启动参数 migration disabled、Runtime Host 0、workers 0；重启后业务 source/pipeline/binding/selection 均 0。
9. 本文件落盘后精确提交并更新 AOS/Prime 上下文；下一波 E13 先判定当前安装激活/配置产品路径和独立运行身份的安全接线，再推进首条正式来源与 SourceSelection 原键审批生产者。没有实际授权源时不拿合成数据冒充首链。

旧 12 Run 冻结、230 L0 挂起；不读取商城源、不手工 run_definition、不重发未知结果、不 push。首链、八场景和发布仍未验收。
