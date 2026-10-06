# 完整 SigningPermit 原文字段门

基线21b6d0d9 / AOS-001382；原publication Task ACTIVE，Owner/lease20:00已核对。方案先修订，范围仅publication_store.py、publication PG测试和本证据目录。

新read_signing_permit(bytea)先执行既有原文canonical门，再检验全部15字段、固定正向tenant/purpose、严格正整数、原Unicode标识符、完整deploymentTarget、精确policy ref、root格式、canonical Ed25519 public key及合法时间窗口。read_signed_time仅接受原Python规范ISO原文，按显式offset换算，保留±23:59原合法边界，禁止零小数和零offset别名、非法日期和超过366天窗口。两个函数均INVOCER/IMMUTABLE/nonSTRICT/pg_catalog，PUBLIC执行撤销，拒SQL NULL；不读取当前时钟或写表。

31项RED均缺新常量；最小实现后31项原生PG通过2.27s。加新函数catalog ACL/NULL后原publication和Source/auth相邻289项通过22.99s。

独立督导指出原Python3.11 json.loads整数默认4300位门遗漏。最初两次新增测试因导入错误失败，均保留，不计逻辑RED。修正测试后真实双oracle RED为4 failed/2 passed：完整许可仅变两个revision，4301/5000位SQL接受而原Python拒绝；4300位均接受。方案补冻结运行配置后，两处SQL限制4300位，未来实际安装仍须独立核Python该配置和Unicode版本，不能宣称已部署门。修复后完整publication+Source/auth相邻295项通过22.92s、7项既有警告。

现有route_supervisor受邀只读独立复审：反例修复后未发现范围内新重大语义问题；明确字段门不验证签名、可信root/permit、parent policy当前性、撤回、真实部署目标或发布权限。当前新增入口纯未认证结构，不创建迁移152、不安装正式publication、不授issuer权、不修改真库/服务。适用浏览器验收：无页面/服务变更，本纯SQL合同不以浏览器或200佐证。

原生隔离实例固定image/network-none/无端口/非privileged/Task label由fixture逐次核；全部私有计算DDL同会话BEGIN/ROLLBACK，最终只读catalog核私有schema0、原aos_ed25519.verify1。已有用户文件未修改，本Task无完整Delivery；Goal/Task继续ACTIVE。

下一关键路径仍为原完整S01–S20批准SQL及可信origin/permit取钥→最终Source发行/消费→共享物理容量与Model评测→b90与自然经营首链。COMMIT时钟与晚提交归属裁决pending，不自行放宽，不把字段门/测试数量当整波或业务完成。
