# AW 配置接续受阻实例正式退休方案

## 当前权威

AW installation `f94b9425-9bc4-4369-8ae3-138c50c9ab81`、generation
`a92f7bb2-3d90-4d88-9632-5fc9a70bd650`，安装 etag5。策略续期后 configuration rev2 已通过正式
configure/enable 写入 Binding rev9/epoch5 `enabled/ready/unfenced`；九路仍指向 AW epoch3 rev120/group147。
definition rev76 disabled，AW attempt=0，三资源 pending。十二 Run 与 Dataset Receipt 保留，Store Receipt、link、
projection pending、running/unresolved/runtime pending 与 canary 均为零。

配置 refresh 历史属于不同的旧 J activation，现有 Owner 与不可变触发器禁止跨 activation/installation/generation
续链；本波不修改历史模型、不绕过门禁，改走既定 fail-closed retirement + direct successor。

## 文件级清单与动作

1. 将已真实验证的 `scripts/a0v_as_failed_retirement.py` 中波次身份与 revision 常量参数化；AS 默认合同不变。
2. 新增 `scripts/a0v_aw_blocked_retirement.py`，固定 AW identity、definition rev76、active Binding rev9/epoch5、
   九路 rev120/group147，且 attempts 必须严格为空。
3. 新增专项测试，锁定单次 disable、禁止 `run_definition`、不修改十二 Run，不接触商城源数据。
4. 串行执行 `preflight → request-disable → process-disable → audit`。请求只经既有安装控制 Owner；处理先读回，
   未知结果不重发，只在 exact accepted 时由正式 consumer 完成 fence/detach。
5. 终态要求 Binding rev11/epoch6 disabled/fenced/unknown、九路 legacy rev122/group149、三资源 released、
   definition rev76 disabled、attempt 仍为 0、全部保存快照与零副作用边界不变。

## 退出条件

专项测试与相关退休回归通过，四阶段 0600 私有结果完整，verification 落盘并精确提交。随后以 AW exact detach
Receipt 为唯一父权威创建 AX direct successor；禁止复用 AW generation、禁止手工 Store 重发、不 push，230 L0
继续挂起。
