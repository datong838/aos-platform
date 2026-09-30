# W5CB4 BG00ct｜签发 attempt 持久 Receipt 文件级方案

## 上位方案与失效模式

231-5 要求未知外部结果只读对账，不得重发；BG00cn 签发必须独立连接，BG00cq 只能精确观察 Event，BG00cs 因缺 attempt authority 禁入。若进程在数据库提交后、HTTP/IPC 响应前断开，Event 可能已存在；若 Event 暂不可见，UNRESOLVED 仍不能证明未发送。本波只实现隔离签发进程本地、先落盘再允许首次调用的 at-most-once 凭据，不接现网或实际 `decide`。

## 文件级顺序

1. 新增 `services/aos-api/tests/aip/test_aip_network_issuer_attempt.py` 先 RED：私有持久目录、exact org/project/proposal/key/requestHash、原子独占创建；相同请求再次尝试拒绝，异内容同 key 冲突；空/损坏 Receipt、符号链接、宽权限目录和文件拒绝；模拟函数崩溃后仍不得再次签发。测试独立临时目录，不用当前库。
2. 新增 `services/aos-api/aos_api/aip_network_issuer_attempt.py`：仅接受 BG00cp 严格 Command、已验签 principal 与专用私有目录；以 tenant+idempotency key 的稳定 SHA256 文件名，`O_CREAT|O_EXCL|O_NOFOLLOW` 写固定 schema 的 exact Receipt，`fsync(file)` 再 `fsync(directory)` 才返回首次授权。已有文件始终不给再次授权；若内容不可校验则 UNKNOWN/禁入。目录必须真实、issuer UID 拥有、0700 且无 symlink；文件0600。只记录请求哈希与主体，不落 JWT 或决策正文。
3. 这只是 at-most-once 前置原语，不提供清理、重试、决定回调或 Event 写入。调用者必须先完成 BG00cr 身份门，再 reserve，再单次 BG00cn 决策；一旦 reserve 发生，任何异常都只能走 BG00cs Inquiry。之后另波 BG00cu 在独立进程/IPC 中组合并进行故障注入。
4. 专项/邻接、隔离安全复审、verification、D-waves、精确提交与上下文同步。现网 API、当前库、迁移、Host/worker/Provider 不变。

## 风险边界

本地 Receipt 仅在持久私有目录和独立 issuer OS 用户下成立；目录丢失/恢复不能被解释为“从未尝试”，必须以外部备份和 Event 对账处置。无法证明正式实例的 OS 隔离前不得启用签发进程。原语通过不等于批准 Event、当前第二 checker 或首链已完成。
