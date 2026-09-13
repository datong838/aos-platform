# 精确目标领取验证

基线39e03945；源码新增 ClaimTarget，可选过滤在同一领取SQL生效。未传参数保持原行为，不赋予任何权限。

Red：新真实PG用例因缺少ClaimTarget失败。Green：automation occurrences两文件28通过；随后新增非法身份参数用例1通过。专用18432隔离schema，无主库变更。错操作/安装/代次均无attempt，正确目标仅领取一次，原租户/禁入/时间/幂等回归通过。

AR2-7：1883扫描、168分类、93迁移，所有错误数组为空。git diff --check通过。

分析Run承接尚未完成；主Host未重启。本变更仅前置领取边界，不将测试计为真实首链验收。下一波连接installed分析命令、当前claim与目标Receipt，并处理未知结果只对账不重发。
