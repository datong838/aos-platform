# AM successor registration 与 cutover 验证（2026-09-18）

## Rules

- 只接受 AL 唯一 detach Receipt 和 groupRevision116；注册本身不可执行。
- cutover 使用固定 operation，严格 approve → prepare → pause → commit → validate → resume。
- 每阶段先冻结 intent；未知结果只 inspect，不重发；禁止 fallback 与外部效应。
- 浏览器结果按事实记录，不以路由 GREEN 掩盖工作台入口缺失。

## 第 1/6 步：registration

AM successor request hash 为 `sha256:8d8470484929d8cae4fb74a9913c5fce4cbe3d40c6931ebb5fe1c0198046009c`，绑定 AM installation `fd28d180-db24-4568-a848-101fcd3aa3c5`、generation `d6bc117e-d19d-4413-beb4-02884206e290`、binding rev4/epoch3 与 AL detach Receipt。注册 Receipt 为 `dd042ffc-6465-4929-9add-1d1137b4183c`，`executable=false`。

## 第 2/6 步：prepare 与 pause

固定 cutover operation `23bc8ec0-1a67-4ae8-9210-de67114f7a6a`。prepare 由 legacy rev89/group116 计算出 AM extension rev90/group117；pause 读回 claimed/unknown/running/pending refs 全空并暂停 claim。

## 第 3/6 步：commit

commit Receipt `9196ac83-6fb0-4a07-949a-3106d67a61bf` 将九路一次性写为 AM generation、epoch3、unfenced、rev90/group117；没有部分路由或 fallback。

## 第 4/6 步：validate 与 resume

validate 读回九路精确匹配；resume Receipt `8769171a-8db0-46f1-8aa6-cdb15f8ade0d` 恢复 claim。AM binding 最终为 rev6/epoch3 enabled+unfenced+ready，definition 仍 rev51 disabled，running/unresolved/runtime pending/dev-org canary 均为零。

## 第 5/6 步：专项与浏览器验收

business/cutover 两个专项测试通过，脚本编译和 diff whitespace 检查通过。浏览器 `http://127.0.0.1:8434/` 可正常加载，组织/工作区精确为 `org-org/dev-project`；AOS v1.6.5 主导航和数据/AIP/本体入口可见。当前侧栏“电商工作台”显示“暂无可见工作台入口”，因此浏览器验收只证明主壳与租户可达，不能记为电商工作台可见 GREEN；该缺口进入保存输入恢复后的目录/安装态复审。

## 第 6/6 步：下一波

下一波转移 snapshot definition：以 AM rev6 runtime、九路 rev90/group117、AL rev51 disabled、recovery rev16、十二 Run 与零 Store 提交为 exact 前置；先生成 AM disabled definition，再以 recovery rev17 enable，保持 `sourceReads=0`。自然 Worker 是唯一 attempt 入口，禁止手工 `run_definition`。
