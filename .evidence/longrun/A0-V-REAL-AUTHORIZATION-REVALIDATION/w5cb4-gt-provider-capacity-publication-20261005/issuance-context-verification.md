# v2签名主体与事务原文格式验收

基线b3fb0714/AOS-001376，原publication Task同Owner/Lease范围。仅原contracts/test加本证据目录；v1保持，明确新增v2，不创建迁移/签发入口/DB授权，不改权威库。

- 首RED：新类型不存在导致26failed/6.67s，完整合法文档单项变异，不用缺字段间接拒绝。
- 最小实现：26passed/6.69s；追加unknown-maker拒绝以及原生SQL验签组合。
- 最终publication/source_contracts相邻：195passed/7既有warnings/17.36s/exit0。显式固定最终隔离验签镜像和r4实例，原始Ed25519签名true，七种格式合法的主体/issuer/audience/认证截止/xid/PID/attempt原文变异均使旧签名false。固定issuerRole另有错误角色格式拒绝。
- 保留原Source所有字段/语义与v1，v1/v2互拒；v2 signed-body parser明确选择schema2。认证截止aware且>issuedAt，仅约束签发认证，不暗改Source全期必须≤JWT期。issuer HTTPS形状/标识、xid8上限、PID严格整数、attempt标准UUID，多余字段/privateKey/verified拒绝。
- 独立督导受邀只读复审无新重大问题；指明后继signer/SQL必须核实际subject/issuer/audience/认证截止及原批准maker、当前xid8/PID/attempt、requestHash和精确待签raw。consumer应核发行provenance与当前授权，不能要求历史xid/PID等于自己新读取事务。
- 只读验后private schema0、测试role0、原crypto函数1。源hash在issuance-context-hashes-and-rollback.json；无UI变更，浏览器不适用。

本次没有验证真实JWT、受控key、实际native事务绑定、Source发布COMMIT或consumer。解析可接受格式合法的不同主体声明，这不是授权。完整Task仍ACTIVE，提交时钟裁决及晚提交归属污染仍未解决，不能helper-only Delivery，不能把195tests称自然首链。
