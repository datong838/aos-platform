# 栖月汇原职责重绑定恢复条件复核

基线 a55dc9732d7d8f3d7aa39667d29fb78b8ad4d850 / AOS-001898。按第十八段方案，仍在原 ACTIVE Task 的证据范围内；不修改 services、当前库、安装状态或运行身份。

原 auth.resolve_principal 解析实际开发身份，原 SignedBIPlanActiveRebindService 在正向与 canary 两 scope 均以 formal authenticated actor required 拒绝，连接计数为零。未构造 OIDC Principal，不把开发 admin 权限当正式认证。当前 API 的原 OIDC GET 返回开发 issuer、JWKS 地址为空、未配置 token URL、grantTypes 为 dev。因此企业登录和独立发布身份接入尚未完成。

当前恢复库 aos_meta_head@a0v_159、cluster 7695302940039200809，仅通过既有有限 LOGIN / aos_runtime 与显式 READ ONLY 查询。栖月汇正向 scope 保留 active 111、uninstalled 24 条安装；active 指针同版的 111 条记录不代表 runtime 已启用。独立查询 126 条 runtime binding，enabled 为零、fenced 为 126。dev-org 没有对应安装或运行绑定。

原 resolver.select 会吞异常，不能仅以 None 推断缺来源。独立脚本采用正常只读 Registry factory，再直接调用原不吞异常的 _approved_rows 查询，两个 scope 的当前 published BI 来源均为零；select 为 None 与原空行结果相符，Registry factory 没有被调用。首次审计的禁止 Registry 调用 factory 因而不是这一缺来源结论的依据。

全部 179 个选定签名包文件保持原 hash；已有八工作台定义和模板继续复用。没有删除数据、重放旧 Task/Run、发布或启用执行。语法、脚本 hash 绑定、结果声明和秘密扫描复核通过后精确提交。该段只确认真实恢复前置条件，不增加原 22/30 实验合同覆盖，不收口完整 Source Task，不声明八工作台可运行或正式系统恢复完成。

下一步继续原正式登录、独立发布来源和当前签名安装的受支持重绑定路径；既有入口信息仍待确认，不重复索要密码。媒体策略 producer/consumer 是另一个已登记候选，实施服务代码前需完善对应方案和精确 Task/Lease。当前 Goal 保持 active。
