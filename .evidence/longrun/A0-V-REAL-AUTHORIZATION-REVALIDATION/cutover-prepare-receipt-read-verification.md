# prepare 原键回读验证

基线135eec2f。初始7失败：6项缺失方法，1项测试试图改不可变历史被数据库拒绝。保留不可变保护，将错误hash注入改为读取结果测试。实现后真实PG与既有合同联合21 passed，AR2五类错误空，diff检查通过。

复用当前注册Owner的安装APPLY权限，先鉴权再查原键；同租户同安装限制、完整既有Receipt解码，历史标识与不可执行标识。未新增业务写入或切换动作。主库授权操作员得到LookupError（尚未prepare），默认user:dev得到DutySeparationRequiredError。最初探针把权限异常误认成另一类导致断言失败；诊断确认实际拒绝正确，无产品权限修改。结果见cutover-prepare-receipt-real-probe.json。

边界：只覆盖prepare历史回读；其余阶段恢复快照、产品HTTP和UI仍待接入。下一波把各阶段既有Receipt解码器组合为只读恢复视图，再接阶段操作，不以重复POST替代未知结果查询。API尚未重载。
