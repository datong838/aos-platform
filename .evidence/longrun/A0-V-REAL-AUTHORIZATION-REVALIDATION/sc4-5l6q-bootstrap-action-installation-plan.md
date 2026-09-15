# 初始化动作随安装到位，而非人工补表

## 实证
H真实商品源更新生成65事件；诊断Host在ecommerce_analysis_bootstrap_action.py:53 → aip_action_store.py:192抛AipActionNotFound。主库meta_action_type中ecommerce_analysis_bootstrap为0行。既有集成测试review_identity fixture直接插入此类型，因此此前绿色测试没有验证安装交付依赖。此为具体缺口，不修改权限检查以掩盖缺失。

## 顺序
1. 保留单次源观察/finally关源；新增scripts/a0v_h_product_pause.py，用当前Policy5原回执走精确审批/disable，停止继续产生重复unknown，保留已产生历史。
2. 核对动作类型声明及安装元数据注册机制，形成最小安装/配置就绪契约，使全新租户无需开发者补表。继续保留运行时当前action snapshot与角色/marking检查；不得遇到缺失时构造假快照或降低门禁。
3. 先补“未预先seed动作类型”的集成测试，再实现适用的注册/就绪路径；安装、幂等、漂移拒绝、禁止越租户及已有正常动作不被覆盖都需验证。必要的新增文件在确定后追加本方案再编码。
4. 通过真实正式入口恢复H业务流，不重发未知。当前首链Run0，源成功不计经营成功。

## 07:14暂停证据与设计约束
源scr-6554bd62601f4790成功65行/9959ms，finally已关闭schedule；H Policy5 disable Receipt 1114f2f9-3b0f-579d-a440-6e8db5e6bfe0@2，hash sha256:69aa23633312a531d02ee7295b730a36cb8fceeaaec0b0bc00cb323d68d6e033。当前H9needs_attention/56pending，Run0；后续若仍有已领取事务结束需再核对最终数。
meta_action_type为无tenant列、无RLS的旧全局表。因此不采用全局seed或手工补一行。方案细化为安装代次/epoch作用域的内部动作目录：在已有精确审批的event-enable事务中自动登记Host初始化动作定义与源控制Receipt，运行时只读该安装的目录并核对来源，已有全局动作不覆盖。当前全局动作快照校验保留给既有记录，新的安装动作快照携带显式目录Ref，不做无来源fallback；原guard还要强制当前安装目录与proposal snapshot一致。
