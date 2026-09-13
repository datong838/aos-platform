# CF2-10 蓝图当前依赖选择验证

基线443ae418。新增AnalysisCompilationSelectionReader，复用规范蓝图验证与当前职责Owner。模板仅匹配当前head的完整蓝图正文hash/profile/frozen，唯一；绑定仅匹配当前职责agent实例及目标skill IDs，逐技能唯一。内层复用阶段/Skill当前读取器，核对原发布Logic与包蓝图，前后重查选择防漂移。

Red缺模块7 failed；Green选择7+蓝图port10+Skill读取8+职责11=36 passed。Owner/Skill/连接均明确替身，验证组合与拒绝，不冒充真实安装全栈。AR2 1893/172/93所有错误为空，memory validate GREEN/AOS-000573，diff --check通过。

额外恢复主库只读SQL确认新蓝图模板hash fdcd7aaa34096b489aa01ac3f314bcc86e878bd866869531bd1106305e43567e 当前匹配0条；旧冻结模板不可代替。下一波CF3-1受当前职责/安装约束的模板幂等准备，随后Task/Brief/Context与编译Saga。CF4真实START仍未完成，CF5部署及CF6业务仍待。未主库写入/部署/push，230 L0挂起。

```text
templateContentHash=fdcd7aaa34096b489aa01ac3f314bcc86e878bd866869531bd1106305e43567e
BEGIN
 current_compatible_templates 
------------------------------
                            0
(1 row)

COMMIT
```
