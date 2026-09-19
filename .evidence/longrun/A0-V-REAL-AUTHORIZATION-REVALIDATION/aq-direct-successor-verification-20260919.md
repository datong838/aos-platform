# AQ direct successor 与冻结十二源恢复验证

## 结论

AQ installation `d6839bf3-55b5-474c-aa21-49966e15db3d` / generation `b31be2a7-36fd-4348-9ff8-10939cc3d1cd` 已由正式 lifecycle 建立，并以 AP 正式 detach Receipt 为唯一前置完成 successor registration、九路由 cutover 和冻结十二源恢复。全过程未调用 `run_definition`，恢复动作 `sourceReads=0`；本波终态 AQ attempt 数为 0。

这只是 AQ 可恢复 Store 自然执行前的权威准备完成，不代表 Store 闭环、经营参谋自然首链或八工作台真实业务完成。

## 安装与 successor registration

- installation：`d6839bf3-55b5-474c-aa21-49966e15db3d`；generation：`b31be2a7-36fd-4348-9ff8-10939cc3d1cd`；
- lock：`sha256:7e338c1ae340333ca42f8f52c9e383b96255a9f9a6d9afc68ae9cb60f83e4f8d`；
- configuration：`795e055b-c3d2-482b-974f-c163561b4587`，`sha256:46305367e828739835509773316e550e7964a9698303267ae751ec348dd88f1a`；
- 安装终态：head etag5 active，binding revision4 / epoch3，enabled、ready、unfenced，3 个资源 live；
- successor registration Receipt：`76da1775-fef7-4d8c-863b-ec9820b155bc`，content hash `sha256:0faba5daaeb5f03ad4e858cffd34fe45d976432cc9888b3a164d847b75a62392`，注册时 executable=false；
- registration request hash：`sha256:efe25a870a60c96c4418c865ab07c32188fe030d496d9e83402a91ee94d2958a`；`dev-org/dev-project` canary=0。

## 正式 cutover

cutover operation `56afe1b2-a69f-4824-ba57-2debab4652e0` 完成 `approve → prepare → pause → commit → validate → resume`。九条 route 从 legacy revision101 / group128 切换为 AQ extension revision102 / group129，目标 Runtime revision6；claim 已恢复，期间 claimed、unknown、running attempt 均为 0。

关键 Receipt：

- prepare：`dd7b8f37-0c08-426e-9bfa-ff6ae223cf37`，`sha256:af1011b765b72ac1fcb7c7544d815a5cf78bfbe05a570b8c3148e2fb65587e0a`；
- pause：`68eb8d3c-6aa5-446a-a0aa-c8ea343dcd9b`，`sha256:46d06c75aa56372da1fb808bf5dc680232cc401bfa75a1e66c3c7f82fe19b5c5`；
- commit：`5cd25d5f-70b5-428c-b12b-88844ea47bdb`，`sha256:7cb675c4429e94b01d0ad73f234759560a6f8e3c61fa451a937b59a10921d370`；
- validate：`e0e90825-bbd4-45ef-a2dc-112e3ca50c0e`，`sha256:a55e7e57d5d0190f05f1015462df09318084ea1899377f2667b6839c0e0191f3`；
- resume：`7983ea5c-e3bb-4fcf-acf0-c23e00fcd2dd`，`sha256:e5b3d001f9afe65b407df51e360b6cde39a9eda34c04e35a0c9aeb2586c3bd87`。

## 冻结十二源恢复

- group：`c5ff1926-45b0-56de-b6b3-07d5b7d053a1`；manifest：`sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`；
- definition 由 AP revision63 disabled 转为 AQ revision64 disabled，再由 recovery 原子续期为 revision65 enabled；revision65 hash 为 `sha256:dc6a6110693b963d39d00f1c1a10cec551e6ec7b0f1c74a2e4c62e402e758815`；
- recovery revision21，hash `sha256:ca728abad4b6c6f276da8eb0dc6e7bd8c07141a4970a4d84bb0e2c5ad782cd21`，request hash `sha256:62a762a2519330bd30da61039ea1903223e1fc67cfa5f71642ba61f0ce87c7d1`；
- 12 个 schedule、12 个 Run、12 个 Dataset Receipt 保持原身份；Run 均为 running，恢复没有重读商城来源；
- enable 读回为 configurationState=enabled、executionAuthorized=false、routingStatus=original_group_pending；
- 终态数据库复核：routes=9、attempts=0、live resources=3、members=12、running runs=12、dataset receipts=12、definition revision65、recovery revision21、canary=0；
- qcursor 在 schedule GET 核验时临时启动；transfer 完成后、renew 前已停止，故 recovery 启用后未抢跑 attempt。

## 测试、浏览器与一致性

- AQ replacement/successor/cutover/saved-recovery 与 Store/cutover 合同累计：68 passed，77 skipped；skip 为未启用的隔离 PG 标记用例；
- `py_compile`、`git diff --check` 通过；一次累计命令使用了不存在的 cutover 测试短路径，收集前退出，随后改用实际文件并通过；
- 8434 `/ontology` 可渲染 AOS v1.6.5 与缓存本体导航；qcursor 按控制边界关闭时页面明确显示“当前离线”、写队列 0，与运行态一致；
- Runtime Host 仍为修复后进程，AQ 运行将使用 strict-link batch 修复；本波没有 Store 写入、关系重发或未知结果重试。

## 下一波

先建立 AQ 自然 attempt 的只读守护合同，再启动唯一 qcursor 领取 revision65。只读核对 heartbeat/lease、12 Run、Dataset Receipt、relationship/link command、Store Receipt、`ecom_link`、projection pending、resources 与 canary；不得手工 `run_definition`，不得重发未知结果。若 succeeded，执行现有 AQ `inspect/disable` 并完成终态证据；若 failed，先界定失败原点和提交边界，再走正式 retire/direct successor。
