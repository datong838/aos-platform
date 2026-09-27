# W5CB4 当前 AIP 定义 durable intent 写入器代码核验（2026-09-27）

## 第 1–7 步：实现、专项、累计及现场

- 编码前方案 `w5cb4-current-aip-definition-durable-intent-writer-plan-20260927.md` 已在 `2853e85e`；上位为 231 A0-V/A1、栖月汇产品方案 9.3。只改 `scripts/a0v_current_aip_definition_publish.py` 及当前专用测试；旧发布器和当前实例配置未变。
- 命令默认只读。当前 signed Receipt 下实际运行返回 `CURRENT_DEFINITION_PUBLISH_READ_ONLY`，目标 `aos_current_preview_20260927`、source `bundle://a0v-current/solution.ecommerce.growth/1.11.0`、contentHash `sha256:3d8817e01f53690adbd58698951c226e8c3917304a9ec4d7eee37d64bf02b328`、state EMPTY、intentExists=false、writes=0。当前库此前独立只读仍三定义表 0、Runtime binding 0。
- 显式执行路径要求 canonical UUID intent；使用签名 Receipt 推导的显式目标 DB 连接，不继承默认 DB；意图文件 `O_EXCL` 建立并 fsync 后再检查库和签名一次，Owner 按 10 Capability→6 Agent→37 Skill 单次写，最后 exact 回读 53 个 ID/revision/source/hash。任何 intent 已存在、当前行非空、漂移、异常都冻结，不换键重发。
- 常规专项+相邻累计 `31 passed, 1 skipped`；被跳过的是 append-only 53 行真实 Owner 测试，它必须在单独的可清理隔离测试库会话中运行。专门隔离 PG 会话 `1 passed, 11 deselected`，逐个 Owner 回读 6/37/10 和 source 1.11.0。测试尝试删除该隔离库中的 append-only 行被数据库保护拒绝，因此测试改为独立会话，由标准项目夹具整体清理测试库；没有碰当前新库或业务卷。`git diff --check` 通过。
- 当前 8080/8434 HTTP 200；本波未重新加载当前 API，浏览器上一波仍显示六角色权威投影禁入，符合“未发布”状态。无前端代码改动，此处不宣告上线验收。

## 第 8–9 步：方案复审、边界和下一波

- 脚本代码与方案一致：不隐式 `--execute`，无第二 Host/worker/Provider/商城源/旧 Run；唯一 intent 先于 DB 写。它**尚未**对当前新库执行，未创建真实 intent，也未发布 53 行；测试 GREEN 不等于当前实例通过。
- 下一波先补命令级故障注入和最后一次当前 read-only 核验，再单次正式运行 `--execute`，若任何未知或部分提交即冻结并保留 intent，单列正式恢复方案；成功才浏览器/HTTP 读回六角色投影与 Runtime 仍禁入，并封存新 verification/commit。不得在本波自动启动 Runtime。
