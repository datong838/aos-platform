# UQ4-C Web固定读取会话

基线91bb1053，m1单人串行、不push、230 L0挂起。新增apps/web/src/api/runtimeWorkshopRead.ts与测试。固定经营参谋operation/七字段target/有界limits；当前租户、账号、角色、内存token及API地址前后比对，资源current检查和AbortSignal必须提供。客户端校验仅展示与迟到响应保护，不替代服务器授权。

同一会话POST最多一次、随机Idempotency-Key保持同次固定；未知POST不自动重发。拿到UUID后仅GET原请求，每次HTTP最多10秒、等待窗口60秒，超时保留UUID并允许继续查询。成功/失败/待完成响应严格schema、scope、请求hash、版本、时间与result形状校验。输出副本不能改变内部请求号。

31 tests passed（读取会话18+目录7+目录Provider3+ExtensionHost3）；整个web TypeScript --noEmit通过；git diff --check通过。覆盖单次提交、未知结果、scope/subject/token/资源/abort迟到丢弃、响应错identity/hash/版本/授权标志/失败码、等待超时同ID继续查、无视abort的网络仍有超时、调用者修改副本不改原ID、取消pause不再GET。测试JSON响应改为每次独立解析以等价真实Response.json，避免测试共享对象制造假服务端变更。

尚未挂入真实页面、没有实际OCI资源/新方法；主库和API保持旧部署。下一波UQ5-A signed RuntimeWorkshopHost与目录路由/身份失效清理，再后继签名growth只读方法和资源交付。原九业务命令不开放，7+1结构保持，最终UQ6真实安装读取/UQ7经营闭环仍未完成。
