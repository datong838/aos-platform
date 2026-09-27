# W5CB4 当前 AIP 定义单次正式发布 verification（2026-09-27）

## 第 1–6 步：前置、唯一执行、独立回读

- 上位：231 A0-V/A1、栖月汇产品方案 9.3；强一致记忆 `AOS-000802` 七项 CURRENT、validate GREEN，eventual Codex note PENDING_ASYNC 不作业务状态依据。方案先于实操，见同目录 `w5cb4-current-aip-definition-single-publication-plan-20260927.md`。
- 执行前 m1 `f68b0ca9`、当前库 `aos_current_preview_20260927@a0v_106`、三定义表=0、Runtime binding=0；默认只读命令返回 signed growth `1.11.0` contentHash `sha256:3d8817e01f53690adbd58698951c226e8c3917304a9ec4d7eee37d64bf02b328`、EMPTY、intentExists=false、writes=0。8080 安全预览进程来自 `a0v_current_preview_http.py --serve`，18181 无第二监听，FLAGS 明确 Cron/worker=false、Runtime Host=0。
- 固定唯一 intent `55f1cce8-73a3-43b6-a834-b25c675d3afc`。命令级无效 intent 先返回 `SAFE_BLOCKED` 且文件不存在、三表=0；发现原代码将 UUID ValueError 泛报 UNKNOWN 后，修为 `EXACT_INTENT_UUID_REQUIRED` 再测。没有对固定 intent 作预尝试，也没有换 intent。
- **仅执行一次**正式命令，返回 `CURRENT_DEFINITION_PUBLISHED_EXACT`：10 Capability、6 Agent、37 Skill，sourceRef `bundle://a0v-current/solution.ecommerce.growth/1.11.0`，Runtime binding 0。唯一 intent 文件已持久留存于当前签名 Receipt 同级；其 ID、目标 DB、contentHash、签名指纹和 snapshotHash 与写前 proof 一致。
- 独立 `BEGIN READ ONLY` SQL：Agent `6/6`、Skill `37/37`、Capability `10/10`（行数/不同 ID/符合 revision=1、resourceId、source 1.11.0、hash 非空）；`extension_runtime_binding=0`。随后默认只读命令显示 COMPLETE、intentExists=true，不执行重复发布。脚本自身逐键 exact hash 回读也已通过，但不以 stdout 代替独立 SQL。

## 第 7–8 步：安全预览与复审

- 停止旧 PID 63869 的 8080 安全预览，确认端口释放后用同一 `a0v_current_preview_http.py --serve` 重启，新 PID 87258；启动回执 `runtimeHost:0, workersEnabled:0, migrationMode:disabled`。8080 `/openapi.json` 200、8434 页面 200、18181 无监听。
- 浏览器 `/aip/model-runtime` 跨页“六角色定义不一致”错误消失，出现“数字同事 0/6 可自动执行、已绑定 0、已启用 0”；模型路由 0、预算/策略仍无配置。`/apollo/assets` 唯一安装仍 approved revision 3、active 指针无、`not_prepared`、尚无运行绑定；八项 Runtime 配置候选均缺。工作台目录无可见入口，继续 fail closed。
- 安装详情另有“电商业务登记服务暂不可用”，只读刷新仍在；未为清此提示绕过配置或执行 Apply。记为下一波定向诊断待办，不把它等同定义发布失败。
- 专项+相邻累计 `31 passed, 1 skipped`；skip 为 append-only 当前发布真实 Owner 测试，已在独立隔离 PG 会话 `1 passed`。本波代码只修无效 UUID 的明确拒绝；无商城源读取、原 12 Run 重放、手工 run_definition、Provider/外部动作、Runtime 启用或删除业务数据。定义发布成功**不等于**六角色可运行、A0-V 准入通过或 A1 自然首链完成。

## 第 9 步：下一波

- 先按 231/BG-00 做“当前定义 → 六角色合法 AgentInstance/SkillBinding/CapabilityBinding 与责任计划”的文件级方案和隔离实测，预算/数据分类/出站/网络/配额等八项配置各按正式 Owner/业务审批推进；优先诊断安装页登记服务提示，但不以边缘提示阻断首链核心工作。保持 Runtime Host/worker 关闭，直到完整准入和授权。
