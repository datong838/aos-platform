# BG-02 包内策略与Case组合验证

2026-09-14，基线fed65f62。新增prepare_event_case_binding复用包内两个权威合同，生成精确下一Case及规范组合hash；无存储/端口调用。当前Case须ACTIVE且策略/方法精确匹配；后继要求Case绑定原策略，不能缺前版或隐式转策略种类。只改变版本、调度引用与审计字段。

事件策略及组合累计36项通过，重复输入结果一致；跨引用/租户、关闭Case、时间倒退、缺前版拒绝。AR2首次扫描提示新模块未分类，补清册新增行和当前hash后重跑：1864模块、164分类，hash/前向/反向/跨层/动态错误均空。未修改历史preHash或运行封印。diff及memory-validate通过。

下一片沿product-event-owner-integration-plan实现同事务持久化。主库038、代码迁移head039，仍无事件策略写函数、实际自然触发或新Run。已签名候选及当前Host不变。
