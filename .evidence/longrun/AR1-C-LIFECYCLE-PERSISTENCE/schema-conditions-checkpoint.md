# AR1-c 签名schema条件检查点

2026-09-06；基线4eb388f4/AOS-000528，沿用主生命周期Lease。

新backend协议固定签名schema-requirements.json，精确记录坐标、hash、signature/evidence、文件字节/大小，拒绝重复键/版本、未知字段、缺声明和含storage的空声明。CurrentSchemaConditions读取本地可信缓存，事务内校验精确安装账本，无网络下载、DDL或许可写；纯内容兼容不变。独立复审指出全局裸包id碰撞，改用共享函数导出的bundle-<canonical hash of publisher/id>，维护/读端一致，禁止裸id回退，跨release保持稳定。此键不是物理表命名隔离或执行许可。

测试：模块缺失Red7failed→7passed/7.65s；schema目标13passed/7.85s；实际签名worker使用临时维护apply_once创建探针表与hash账本后verify，1passed/11.54s，替换旧True条件回调。累计525passed/6既有warnings/92.76s/exit0在身份补充前完成；身份及反证增补后的最终受影响目标17passed/39deselected（包含同id异publisher拒绝、裸id拒绝及跨release身份稳定）。独立Prime只读复审确认身份修复方向及其余内部边界，不代替测试执行。

仅专用临时schema执行测试维护，无共享迁移或真实业务写；无页面改动/在线后端重载，浏览器旧冒烟不冒称此代码验收。未调用Provider、未产生费用或发布。安装验证仍disabled/fenced，不开启业务端口；平台兼容、配置启用、派发与恢复等后续未完成。新增业务场景0，整波IN_PROGRESS。下一段配置引用、配置更新fence与启用前置校验。
