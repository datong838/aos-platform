# W5CB4 E11 验证：SourceSelection 精确候选编译器（2026-09-28）

## 结论与边界

E11 的**纯编译切片完成**：唯一固定 snapshot 图与同一包版本、导出路径、SHA-256 相符的 mapping/schema/masking 三元组才生成 `prepared/readOnly=true` 草案。零解、多解、图/来源/租户/哈希/版本/导出路径漂移均拒绝。编译器不读 DB、商城源或网络，不写 Selection/执行/Receipt，不启动 Host/worker；旧 `PipelineSourceSelectionOwner` 未变，真正审批仍必须原事务复核全部当前权威。当前卷授权源0、正式管道0、绑定0，因此**没有实际草案或审批产生，首链未通过**。

## 9 步证据

1. 复习 231/231-9、栖月汇产品方案和 E09/E10，核对 Owner/资产/路由与当前卷；当前 `m1` 计划提交 `b754c76c`。
2. 文件级计划 `w5cb4-e11-source-selection-candidate-compiler-plan-20260928.md` 已先提交；最终只新增 `pipeline_source_selection_candidate.py` 与 `test_pipeline_source_selection_candidate.py`，未修改 Owner/路由/图存储。
3. 编译按原 Owner 的 `derive_mapping_read_spec`、`verify_graph_read_spec` 规则校验，计算原 `_digest` 图哈希，核对原包导出路径、字节 SHA-256、版本；最大每类 16 候选、每资产 256 KiB。
4. 专项 `test_pipeline_source_selection_candidate.py` 14/14，通过零候选、多候选、不同图、来源、租户、哈希、导出、版本、超界和无效 schema 负例。
5. 邻接累计：候选、原 SourceSelection 资产/Owner/合同/Store、E10 准入、E09 回执共 144/144 通过；`compileall` 和 `git diff --check` 通过。另试跑 `test_pipeline_registration_truth.py` 时 2 项夹具启动错误：当前 shell 的旧 `signed-bundles-niushop-1.5` allowlist 指向已不存在的 `.aos-recovery-20260913` 目录；它不涉及本波模块。未恢复旧历史目录、未更改真实服务配置，后续应将该测试隔离到当前 fixture，不把这两项算绿。
6. 浏览器 `http://127.0.0.1:8434/data/pipelines`：正式来源为空、当前管道 0/0、页面提示先去数据源管理；没有审批按钮或执行结果。重启后再次刷新读回相同状态。
7. 一致性复审：计划中的纯函数/唯一性/失败关闭均已实现；“当前安装/源/配置已核验”不由此函数证明，必须由 E12 可信只读生产者与最终 Owner 承担。调用方如传入未核验资产不能据草案获得执行权；不得把该草案直接作为 UI 执行许可。无数据库迁移或旧业务路径改动。用户已有 dirty 测试/两个 w5c8i 文件未触碰。
8. 当天最新代码/原命名卷完整重启：容器 `aos-a0v-recovery-pg` 仍挂原 `aos-a0v-recovery-pg-data`，DB `aos_current_preview_20260927` 为 `a0v_109`；API 8080 `GET /v1/health` ok、`GET /v1/ready` ready，Web 8434 HTTP 200 且浏览器可用；18181 无监听。API 以 migration disabled、Runtime Host 0、worker 0 启动。原租户安装 1、源 0、管道 0、运行绑定 0、Selection 0。误探 `/health` 得 404，改用正式 `/v1/health`，不是服务故障；Web 首次手工启动碰到已有自动重生的 8434 而尝试 8435，已终止多余 8435，现只保留 8434。
9. 本文件落盘后精确提交代码和证据；下一波 E12：在不冒充 Web 超管/旧代身份的前提下建立可信只读当前候选读取与产品入口，明确原键对账；若运行身份和正式来源仍缺，继续 fail closed，不在主库造样本。

未完成：当前卷真实授权来源登记、正式 SourceSelection/RuntimeControl/ScheduleBinding、自然 Occurrence→Case/Run→建议→内容→评审→复盘、八场景和发布裁决。旧 12 Run 不重放，230 L0 仍挂起，不 push。
