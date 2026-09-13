# 切换历史产品GET接口

基线890677ac；现有Owner已具备当前权限与同事务历史校验。新增安装下GET /ecommerce-growth-cutovers/receipt及/history，使用Idempotency-Key原prepare键，actor/scope只来自已认证Principal。读取服务由控制面注入，未配置503，不回退普通数据库。无POST、无If-Match写语义、无自动重试。

文件：services/aos-api/aos_api/routers/bundle_runtime_installations.py、tests/extension_runtime/test_ecommerce_growth_cutover_http.py。错误安全映射：不存在404、当前权限403、历史冲突409、不可用503；SQL/内部错误消息不透传；保留原登记接口行为。输入缺失/重复key拒绝、规范路径校验脱敏、principal身份传递、OpenAPI唯一接口、自测联合现有登记和Owner。

自测通过后提交，再通过现有受控启动器重载API18181（旧进程PID需核对），安装与Host容器不重启。重载失败恢复旧受控启动入口，不推代码。实际GET默认账号403、健康200，浏览器查看安装状态；不得冒用账号或改权限来演示可见回执。下一波写接口方案需对原key回放也检查当前操作权限，精确审批和Scope由Owner保证。
