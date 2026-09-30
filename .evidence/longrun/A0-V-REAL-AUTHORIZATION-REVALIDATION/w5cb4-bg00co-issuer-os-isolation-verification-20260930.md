# W5CB4 BG00co｜签发进程 OS 身份隔离门验证

## 现场与 RED

接 AOS-000944，复习 231-4/231-5 与 BG00cj–cn，先写 `w5cb4-bg00co-issuer-os-isolation-plan-20260930.md`。当前 API PID65249 与 BG00cm 克隆的私有 issuer 凭据文件均属同一系统用户；0600 文件在同 UID 进程间不隔离。新增专项初次 RED：缺门模块，pytest 收集退出2。没有读取凭据内容或改当前库。

## 最小实现、实测与回归

`scripts/a0v_network_issuer_identity_gate.py` 只读 `ps` 实际 UID、文件和父目录 `lstat`、macOS `ls -lde` ACL 元数据。API/issuer UID 必须不同且都非 root；凭据普通文件0600、父目录0700、owner 均为 issuer UID，无符号链接或扩展 ACL。解析/权限/进程异常均输出 `ISSUER_OS_IDENTITY_NOT_ISOLATED` 并退出2，不输出文件内容。当前 API PID65249 与同 UID 候选、BG00cm 私有文件的 CLI 负例退出2。合成不同 UID/权限的单测只证明算法，不能作为正式 OS 部署验收。

专项2 passed；HBA/DB门/producer 邻接合计20 passed、2 skipped、7 warnings，退出0；`py_compile` 和精确 diff check 退出0。没有更改当前 API/PG/Web 进程、issuer角色或克隆凭据。当前实例仍签名安装approved、binding0、issuer NOLOGIN/HBA trust，Host/worker/Provider关。

## 未完成

独立 OS 用户、发行进程、私有 socket/peer 验证、真实 OIDC/第二 checker 与签发请求/Receipt幂等对账均未实现。下一波 BG00cp 做严格请求合同和进程边界；当前实例缺合法 authority 时维持禁入，首链未证明。不读商城源、不写dev-org、不重放旧Run、不手工run_definition、不push。
