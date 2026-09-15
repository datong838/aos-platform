# F 新版 API 与业务入口接管

Rules：m1单写，先方案，真实凭据，不push，230 L0挂起；F已ready/enabled，不能再重启Host造成不必要禁入。

1. 新增 scripts/a0v_growth19_product_controlled_api.py：加载原product受控API配置，仅将bundle root固定到已发布growth1.9签名目录，保持原账号/租户/权限/凭证预检和端口18181。测试确认原模块默认路径不变、新模块检查路径固定且沿用权限校验。先check成功再只重启受控API，Host继续运行。私有输出独立保存。
2. 新增F专用业务入口控制脚本，复用正式Registration/Cutover服务；固定F安装/代次、新幂等键/审批/切换ID，先读当前legacy分派组版本，不继承E的expectedGroupRevision=1。旧E注册按服务撤回，取得新F注册Receipt；exact方案审批必须绑定当前组版本/九操作/安装锁/代次/epoch/策略和注册Receipt。逐步prepare/pause/commit/validate/resume，任何漂移拒绝，结果未知先读Receipt。
3. 另行接可选event-control扩展审批/Receipt及绑定更新；复用真实数据与业务Case的来源关系，安装更换不能伪造新业务事实或手写完成态。F首链从真实数据更新验证自然触发；旧Case/Run历史保留。
4. 每阶段配置/测试/运行证据分开，先完成API根与注册切换，再补实际event-control执行清单。最终八工作台真实场景、人工评审续跑、复盘/Wiki和连续观察仍为退出条件。
