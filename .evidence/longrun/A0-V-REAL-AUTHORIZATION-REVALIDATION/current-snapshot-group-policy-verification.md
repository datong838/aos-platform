# 当前组规则资产边界验证


SC4-5g5：PipelineSnapshotGroupPolicyOwner完成，全部当前控制内按原installation/artifacts/release policy验证同包导出JSON exact ref、文件字节哈希、公开字段及完整对象集合；执行后再查策略再由GroupOwner复验控制。59组合测试通过3.89秒，补public projection隐匿反例后新文件16项通过3.47秒（合计覆盖60项）；AR2扫描1916五类错误空，AOS-000573 validate GREEN。测试安装/签名资产为明确doubles，不宣称主真实发行资格通过。本波无源调用或业务写入。下一项：只读消费已持久化组原输入，绑定manifest/规则hash和原时间后生成关系assessment，缺input不主动读取源，再关系持久化与原应用Owner。

错租户/安装包/导出路径/版本/哈希/资源类型/重复JSON/缺类型/缺公开字段/发行否决均未进入业务回调；回调中资产或发行资格变化拒绝返回，生成器拒绝。主包未安装，旧单表SourceSelectionOwner未修改。路径规范化防目录穿越，读取上限256KiB。
