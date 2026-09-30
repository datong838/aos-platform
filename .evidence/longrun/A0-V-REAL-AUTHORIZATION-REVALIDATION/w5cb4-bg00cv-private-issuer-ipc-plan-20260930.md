# W5CB4 BG00cv｜私有 issuer IPC 与 OS 身份门文件级方案

## 上位合同与现状

231-2 要求隔离运行和受控 IPC，231-4 要求独立低权限 DB 角色，231-5 要求未知结果先对账；BG00co OS 身份预检当前同 UID 拒绝，BG00cr/cu 已有外部 JWT、持久 attempt 与单次决策组合，但尚无私有进程。现网 API 和 issuer 若同 UID，单靠 Unix socket 路径权限无法形成独立凭据边界。当前正式 IdP、独立用户和 checker 缺失，所以本波先形成 test-only 进程/协议与负例，不切现网。

## 文件级计划

1. 先核对 macOS `getpeereid` 能力、现有 `extension_runtime/ipc.py` 严格帧协议、`a0v_network_issuer_identity_gate.py` 和 clone 凭据/HBA，冻结 API UID、issuer UID、socket owner/group/mode、私有目录及 listener 启动器合同。实测 Python `socket.getpeereid` 不存在，macOS libc `getpeereid` 可用，须通过 `ctypes` 读取内核 peer 身份且失败封闭。不同 UID、非 root 与 credential file 0600/parent0700 是启动前必需；peer UID 必须精确匹配批准的 API UID。路径/组权限不能代替 peer credential。
2. 新增 `services/aos-api/tests/aip/test_aip_network_issuer_ipc.py` RED：非 Unix socket、无 peer credential、相同 UID、root、非预期 peer、超大/重复 JSON、未知方法、带请求角色/DB 凭据字段均拒绝；超时/截断关闭连接。测试同 UID 现场只能验证拒绝，不能当正式跨用户通过。
3. 最小新增 `services/aos-api/aos_api/aip_network_issuer_ipc.py`：只接受固定 `inquiry` / `decide_once` 两个方法及 BG00cp 严格 DTO，bounded frame、短超时、一次请求一次响应；listener 自己注入 BG00cu 可信 DB factory/attempt dir，不从 wire 接受路径、角色或厂商凭据；错误只返回固定 code，不泄 JWT。若没有独立身份/正式配置，入口在任何 DB/Receipt 前拒绝。
4. 隔离克隆测试与故障注入、方案/代码复审、verification、D-waves、精确 m1 提交、上下文同步。当前库只读，Host/worker/Provider 关闭；正式服务启动与 HBA/API 角色切换另立备份+双克隆+零执行波。

## 不足与停线

同 UID test-only 负例、协议单元测试和 clone 只读查询不能证明正式 IdP、跨 UID 凭据隔离、真实第二 checker 或 Approval Event 正向。若 OS 当前无法提供独立 UID 与受控 peer credential，正式 listener 不启动，继续做可独立完成的产品/配置首链项，Goal 保持 active。
