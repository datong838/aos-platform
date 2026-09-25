# W5c9m｜分派兼容基线验证收口

1. 复习 231、W5c9l/route 优先匹配规则与零执行边界。
2. 方案先提交 `m1@ce3737ac`。
3. 静态审框架 `_IncludedRouter._match` 与既有路由优先测试；不按注册顺序凭空判业务结果。
4. 一次隔离纯匹配：十组精确碰撞代表均先者匹配，Dataset detail 同样先 `wave_ext`；另定位 7 组参数形状碰撞，含 POST/PUT。无 endpoint 调用。
5. 无代码改动，专项为无副作用 matcher 基线；累计测试不冒充本波结果。
6. 方案/兼容复审：文档修复不得改变先匹配者，不得意外激活旧不可达写端点；需要锁住 schema 当前选择。
7. 8080 业务浏览器离线，18181 未请求业务接口。
8. audit/verification 精确提交、D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9n：先方案/文件级测试清单，再做最小文档单一权威修复和负例；原组 ACK/closure 冻结。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
