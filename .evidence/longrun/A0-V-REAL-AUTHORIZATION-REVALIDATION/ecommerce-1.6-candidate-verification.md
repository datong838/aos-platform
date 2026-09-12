# 三包完整注册候选验证

2026-09-12，延续已批准的 Runtime Host/重新首装方案。

新增候选 domain 1.2.0、Niushop 1.2.0、growth 1.6.0；原候选不变，operations-base 1.2.0 复用。三包声明 1/2/9 个 API；growth 同时注册签名 Manifest 中的导航/UI。宿主完整 exact registration 规则没有修改。

生成器在复制前校验三个历史 tree hash、拒绝覆盖目标，升级依赖和八个内部自引用。构建预检比较完整 contributions 和 API 字段。资格阶段使用原有 persistent session，创建前将唯一资源身份写入仓外 0600/fsync journal，随后进行注册、heartbeat、cleanup；失败保留 journal 供观察，不宣称成功。

本次 22 项测试通过：声明漂移拒绝、生成器可复现、历史快照校验、签名资格流程、八工作台与十二 API 清单。真实 OCI qualification 尚待下一步，不以注入式单测代替运行证据。

候选 tree SHA-256：

- domain 1.2.0：c4eee495804491e7a67360c2ba1c76a8c3937aee90ed44501e9ac0a00f311fb7
- Niushop 1.2.0：0681f18c4191597498a5ecdab32c31a20ee4918ac328bef92ac53d8e8b015749
- growth 1.6.0：84304e72cab728d8470dff55a837f1b63e0c424da0ab4ee65fd3268ba50b1c3a

下一步：隔离 OCI build 与三包真实 Session qualification，再做 Registry successor 和正式首装。
