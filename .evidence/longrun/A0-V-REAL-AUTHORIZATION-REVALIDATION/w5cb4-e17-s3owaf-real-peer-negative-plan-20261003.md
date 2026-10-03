# s3o-w-af 第一切片｜真实 Unix peer 负例与正式来源复核

## 上位依据与边界

- 231-9、栖月汇产品方案、D-wave s3o-w-af、632 接续。私有 BI issuer 的真实不同 OS UID 正向、正式 IdP/DB 身份仍未证明；当前真库只读，Host/worker/Provider 关。
- 本机 `sudo -n -l` 返回 `sudo: a password is required`，不能借 sudo 人为创建第二正式身份，也不能用 monkeypatch 的合成 peer 宣称正向。仅用当前用户和一次性私有路径验证真实 macOS 内核 peer 的错误 UID 负例，再核现有正式来源，不改当前服务或 ACL。

## 文件级计划

1. `services/aos-api/tests/aip/test_aip_bi_plan_issuer_ipc.py` 增加真实 AF_UNIX 监听/连接，期望 API UID=当前 UID+1、issuer UID=当前 UID。由内核 `getpeereid` 返回实际当前 UID，必须在读帧/dispatch 前拒绝，关闭连接；核 socket 0750 目录/0600 凭据、结束时路径清理。该单项是负例，不能替代真实不同 UID 正向。
2. 如测试暴露缺陷，先保留 RED 输出，最小修 `aip_bi_plan_issuer_ipc.py` 或 `aip_network_issuer_ipc.py` 的精确错误点；无缺陷则只增加测试与证据，不为刷新进度改业务逻辑。
3. 复查仓外正式 IdP、DB 角色凭据、role→scope+subject 来源的当前候选，只记录是否存在与权限形状，不打印/复制秘密。专项/相邻回归、方案/代码复审、verification、m1 精确提交、AOS/Prime/D-wave 更新。正式正向若仍不可执行，只阻该实例并转下一已登记安全项。
