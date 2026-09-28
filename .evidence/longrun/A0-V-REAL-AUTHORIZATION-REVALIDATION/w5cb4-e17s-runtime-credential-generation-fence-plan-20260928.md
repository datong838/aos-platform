# W5CB4 E17-s｜三身份凭据预检至连接期代次门文件级方案

## 上位方案与问题

E17 正式三身份、E17-l 当前签名/物理数据库交叉预检、E17-p API 内嵌 Host 门要求 Web/Runtime/Directory 三身份独立且同指当前权威库。E17-q 发现：子进程预检读取受保护文件后，API 选择器及运行期连接重新读取相同路径，预检后替换同结构 0600 文件可改变实际连接身份。当前无正式凭据或 assignment，不能用历史文件证明正向 Host。

## 最小改动

1. `services/aos-api/aos_api/extension_runtime/runtime_connections.py`：读取受保护文件时从同一打开的 descriptor 提取无密钥文件代次 `(device,inode,size,mtime_ns,ctime_ns)`，校验读取前后代次一致；允许专门的预检调用同时返回 DSN 与代次。API 进程只在 E17-l 预检及物理 authority 校验后锁定精确绝对路径和代次；之后每次读取该文件都检查代次，路径改变或文件替换/原位修改固定拒绝，不将 DSN/密码/内容摘要输出。现有无 pin 的测试/Host disabled 路径行为保持；正式启 Host 路径必须设置 pin。
2. `scripts/a0v_current_runtime_host_preflight.py`：在本次三身份实际连接所用文件打开时取得代次；只在 GREEN 报告加入无密钥 `credentialFileGeneration`。文件在连接期间变更要阻断，避免报告与实际身份脱节。
3. `services/aos-api/aos_api/asset_registry/control_wiring.py`：仅 API Host enabled 且签名/数据库 authority 均通过后，用报告代次固定本进程文件；不一致返回原固定 INACTIVE。独立 Host 同样经过此选择器，不需旁路。报告不对 API 用户暴露代次。
4. 测试先 RED：受控 0600 文件预检后同结构原子替换及原位改写必须拒绝；当前绿色报告代次不符时 selector 不继续；关闭 Host 仍无凭据 IO。专项及邻接回归、当前实例无正式凭据只做缺口负向，Host 保持关闭。

## 安全与回滚

代次是非秘密元数据，只出现在进程间预检报告，不是授权身份本身；真正身份仍由物理 DB 权限/角色/assignment/配置检验。文件轮换必须停 Host、重新执行完整预检再启动；运行中漂移安全阻断连接，不能自动接受新凭据。拥有同一文件系统管理员权限的恶意 actor 超出本门防护范围。回滚需要保持 Host 关闭。旧 Run、商城源、当前库写入、dev-org、Provider、230 L0 均不触碰。
