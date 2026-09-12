# 维护替换命令入口验证

2026-09-13 04:04，父基线 e899120f，m1 串行，无 push。

计划见 niushop-1.5-maintenance-replacement-plan.md。本次仅脚本和测试修改；新增固定 disable-parent / prepare / verify / observe。旧实例必须 active@7、指定 generation、binding@4 enabled/unfenced；新版必须指定 ID、approved@3 或 applied@4 且无已提交 binding。所有写操作仍由 RuntimeDisableService / RuntimeLifecycleService 处理，明确使用已有独立 runtime_worker_connection，避免通用构造器默认库连接。未新增成员或权限。

首轮缺少 command_target 的 7 项测试失败；实现后 7 项通过。补齐新阶段和不可覆盖文件后 18 项通过，与原首装/API 检查共 31 项通过。新增 Owner 结果不明测试后命令测试 19 项通过：第一次请求异常保留不可覆盖的 0600 命令，第二次不会再调用 Owner。7 条既有告警保留。单测不充当真实切换证明。

实际 observe v1/v2 和 command-preflight 均完成，只读正租户两实例。04:03 前驱 exact ref、绑定@4/epoch3 enabled/ready，关联计划 enabled=0、未停 executor=0；新实例 approved@3，无操作/绑定/资源。资源历史包含已释放旧记录，不能把全部历史行当当前容器。未停用旧实例、未重启 Host/API、未请求新 prepare。此次没有商品首读或八工作台业务运行。

接下来正式 disable-parent，确认禁入及 drain 完成；再停止旧 Host、确认资源释放，唯一新 Host/API 使用新签名根和当前代码。结果不明只 observe，不重发。配置/enable 仍须逐步当前引用校验。真实商品 NULL 内容兼容和后续自然业务链仍待验证。
