# W5CB4 BG00cg｜当前预览 API 受限登录启动器方案

## 依据与范围

按 231 主计划、231-4 数据权限、231-5 审批/恢复、BG00cf 隔离证据，当前 `scripts/a0v_current_preview_http.py --serve` 在只读签名/安装预检后仍以 `aos_app` SUPERUSER 服务。当前卷 a0v117 只读，Host/worker/Provider 关闭。受限身份在独立完整克隆已通过 API 生命周期/只读 Store，但正式角色和切换尚不存在。

## 文件级施工

1. `scripts/a0v_current_preview_http.py` 新增 `--serve-limited --api-identity-file` 独立路径。身份文件只记录 host/port/db/user/pgpassFile，无明文密码；文件及 pgpass 必须是普通文件、0600、可信拥有者，目标必须本机当前卷端口和当前库。用受限连接只读核 `session_user` 非超级用户/非 BYPASSRLS/NOINHERIT、仅可成为 `aos_runtime`、不可成为 `aos_app`；直读受保护表和 `SET ROLE aos_app` 必须拒绝。任何不符 fail-closed。
2. 签名/安装预检在短寿命子进程完成；服务主进程不调用 owner 凭证加载器。子进程仅返回非密钥预检 JSON，服务主进程设置无密码 `AOS_DATABASE_URL`、`PGPASSFILE` 路径、禁运行 FLAGS，然后 exec API 服务。旧 `--serve` 路径仅供当前未切换实例维持已有服务，不能作为受限验收结果。
3. `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py` 先 RED：身份文件模式/目标、错误 catalog/越权、预检子进程隔离与服务环境无密钥。再最小实现、专项及邻近回归。隔离克隆再测受限路径；当前实例绝不切换角色或连接。

## 退出与后续

受限路径的静态/隔离验证与旧路径不回归可完成 BG00cg 代码门；正式现网切换需要新一致备份、独立全库克隆、零执行窗口另波处理。普通 runtime 仍能写网络 Event，必须继续拒绝将受限登录等同审批签发。缺第二真实 checker/八配置/自然首链继续待办。
