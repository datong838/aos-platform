# 原输入哈希兼容修复专项

基线66158206/AOS-001611，先复习原Input producer encode(sha256(raw),hex)、原Suite/Intent raw64证据。新准备表误要求sha256前缀：R1 26.13s失败在runtime schema禁入，属于诊断脚本权限路径错误，不作业务RED；独立回读prepared0/NOLOGIN后，仅改catalog读取走原admin并冻结实际conbin，由原runtime在无私表访问的标量表达式执行CHECK，不放宽权限。R2实际业务RED25.84s，原case输入743ba8...由实际CHECK拒绝；独立rollback/Source1保留。

最小修复只有authority.py新prepared_call_occupation.input_hash正则删前缀。content_hash、原Input/Intent/Source/预算/deferred拒绝及默认migration均不变。新独立全bootstrap159 R3原Source/SCRAM/两原批准parent/2case4leg完整准备及旧Source全部测试1PASS69.83s；实际已安装CHECK接受原raw64，拒绝prefix/短hash/uppercase；runtime五表权限拒绝继续通过。纯契约相邻318PASS0.72s，7既有warnings。

独立只读R3：原plan xid aborted，call/plan/debit/Intent0，Source1，occupation NOLOGIN零membership，31旧容器ID/启动/卷/端口相同；AST与gitHEAD一处字段修正精确比较PASS。原代码prefix与所有其他函数未改。新call producer/实际占用/费用分配/unknown/完整finalizer仍没有，本修复不作调用授权、完整父Task或自然首链通过。无UI，浏览器不适用；正式库/服务/Provider未改。
