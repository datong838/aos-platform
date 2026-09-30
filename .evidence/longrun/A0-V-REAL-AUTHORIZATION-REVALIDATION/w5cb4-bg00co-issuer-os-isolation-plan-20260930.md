# W5CB4 BG00co｜签发进程 OS 凭据隔离文件级方案

## 依据与边界

复习 231-4 非 owner 专用角色、231-5 人类批准和 BG00cj–cn。BG00cm 的 issuer SCRAM 凭据位于私有0700目录/0600文件，但当前 API 与测试探针都由系统用户 `ddt` 运行；同 UID 的两个进程可读同一0600文件，不能当独立签发进程证明。当前真实库 HBA trust/issuer NOLOGIN，正式 OIDC/第二 checker 不存在；本波不启当前 issuer。

## 文件和 RED→实现

1. `services/aos-api/tests/aip/test_a0v_network_issuer_os_isolation.py` 先 RED：以当前 API PID 与同 UID 候选、BG00cm 私有凭据路径做只读探针，必须返回 `ISSUER_OS_IDENTITY_NOT_ISOLATED`；同时覆盖 root API、同 UID、符号链接、凭据文件或父目录权限过宽和 owner 漂移。合成正例只验证判定算法，不代替真实分 UID 部署。
2. `scripts/a0v_network_issuer_identity_gate.py`：只读读取两个存活进程的实际 UID、凭据文件/父目录的 `lstat` 与 macOS ACL 元数据。要求 API/issuer 均非 root 且 UID 不同、文件0600及父目录0700均由 issuer UID 持有、非符号链接/普通文件且无扩展 ACL 授权；失败封闭，CLI 不读取或输出凭据内容、不修改文件/进程/库。
3. 用当前 API PID 和 BG00cm 克隆私有路径运行实际负例，退出2。专项及邻接回归、`py_compile`、diff check 后复审。当前系统若没有独立发行 UID，只保留禁入和后续部署要求；另波再接真实 issuer 请求/Receipt 接口。

## 止损

只读代码和测试；当前库/卷不写，测试克隆现状不改，不接商城源、不写 dev-org、不启 Host/worker/Provider、不重放旧 Run、不手工 run_definition、不 push。不能用 mock OS 身份或同 UID 0600 文件宣布正式隔离通过。
