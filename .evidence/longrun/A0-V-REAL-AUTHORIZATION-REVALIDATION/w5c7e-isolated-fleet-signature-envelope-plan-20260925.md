# W5c7e 隔离 Fleet 签名信封验证方案（2026-09-25）

## 上位与边界

复习 W5c7b/c/d：真实控制面清单及独立 fleet trust root 尚不存在；现有 Registry Ed25519 只签发布物。W5c7c 结构完整亦永远 no-authority。本波不接真实 Host、closure、数据库、部署或包 Registry，不读取商城源行；230 L0 挂起、dev-org 仅零 canary，m1 单写不 push。签名正确只证明“指定公钥签过指定字节”，**不能证明全机覆盖、旧入口禁止重启或 closure 授权**。

## 文件级九步

1. 复习 W5c7b/c/d、签名库及产品/技术上位 231/231-9，确认不复用 `AOS_BUNDLE_TRUST_ROOTS_FILE`。
2. 先提交本方案。新增纯模块 `scripts/a0v_w5c7e_fleet_signature_envelope.py` 与测试 `services/aos-api/tests/extension_runtime/test_a0v_w5c7e_fleet_signature_envelope.py`；新增 verification。仅这三个文件，最小改动。
3. 纯验证器接收显式注入的**fleet 专用** trust-root 表（无环境/文件/网络/DB 读取），要求精确信封字段、`aos.fleet-signature/v1` 域分隔、key ID、Ed25519 64 字节签名和 canonical JSON；先执行 W5c7c 时窗/成员结构检查，再验签。通过后仍固定 `automaticAction=false`、`topologyComplete=false`、`closureAuthorized=false`。
4. 专项测试含有效 isolated key、篡改、错误 key/namespace、过期、未知 key、畸形 base64/签名长度、自报授权字段、输入不变；任何异常 fail closed。不得产生真实凭据或落盘私钥。
5. 跑专项与 Host/closure、W5c5k–z/W5c6a–z/JDBC 累计回归；临时 PG 用后停止。旧 Schedule 长测 300 秒边界不在本波重发；既有不终态只记风险。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷待同步写操作。
7. 复审计划/代码/真实 gate：验证器不可能让真实 closure 从 false 变 true；独立签名根的正式生命周期、资产覆盖与逐节点读回仍未实现。
8. verification 落盘并提交后 CAS 更新 docs/AOS 上下文和 Prime 独立长记忆，读回一致性。
9. 下一波 W5c7f：先方案，梳理 trust-root 轮换/撤销/防回退的隔离合同与正式控制面接入缺口；不借此启动真实 closure。

停止条件：验证/提交结果未知、签名来源漂移、真实数据/Host 变化或待同步写操作需要冲刷时冻结边界；不得猜测重试或手工 `run_definition`。
