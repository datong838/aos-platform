# s3o-w-x 第一切片｜BI 私有发行线协议门

## 上位合同与边界

- 231-3/231-9、D-wave s3o-w-x、619–621 要求 BI prepare/rebind 只经独立发行进程；每请求外部 OIDC、不同 OS UID 的内核 peer、受保护路径/凭据、至多一次原 Receipt 对账。当前 HTTP 默认503，真实库只读，Host关闭。
- 既有 network issuer 有经检验的 Unix kernel peer、有限长度帧和私有 listener；`aip_bi_plan_issuer_contracts.py` 与 s3o-w-v 编排已有严格命令及只读未知结果；s3o-w-w 有 BI 专用 DB 身份门。此切片复用 transport primitive，不复制 UID 安全机制，不连接当前 DB/HTTP。

## 文件级施工和判据

1. `services/aos-api/tests/aip/test_aip_bi_plan_issuer_ipc.py` RED：只接受精确 version1、`prepare`/`rebind`、无重复 JSON key/额外 actor/role/path/DB 字段、有限字节；错 peer 在读帧/注入 handler 前拒绝；同 UID 不能伪隔离；响应不含 bearer/异常/DB 细节。测试替身仅验证线协议，不能作跨 UID 正向验收。
2. `services/aos-api/aos_api/aip_bi_plan_issuer_ipc.py`：调用现有 `require_issuer_peer` 和 `read_issuer_frame`；严格解码 Pydantic 命令，显式注入至多一次 handler，固定期望 TenantScope；一连接一命令、一份小响应，仅 `observed/unresolved/conflict` 状态。错误统一 blocked，发送失败不重试/不改 marker。
3. 专项/相邻 network IPC 与 BI 命令/编排回归、编译/diff/方案复审；verification、精确提交、D-wave/622/Authority/Prime。

## 后续进程门

下一切片仍要单独建立有限进程配置、0700/0600 attempt/凭据、0750 socket 目录、不同 OS UID 真实 kernel peer、外部 OIDC 启动门，并把独立 DB 连接工厂构造原服务和 Reader；签名 full schema 克隆正反/恢复之后才考虑正式当前卷。当前真库不得写，不用测试身份放行 HTTP。
