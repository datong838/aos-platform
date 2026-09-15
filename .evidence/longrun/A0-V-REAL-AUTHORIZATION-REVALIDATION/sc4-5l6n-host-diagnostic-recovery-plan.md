# Host 诊断加载与正式恢复

任务 SC4-5L6N-HOST-DIAGNOSTIC-RECOVERY-20260916，m1独占，不push，230 L0挂起。
G已暂停Policy3/4与源schedule；21unknown及109pending保留。安全诊断代码794612aa尚未加载到PID93538。不得注入进程或声称已加载。

1. scripts/a0v_g_diagnostic_retirement.py 固定G installation/generation、runtime6/epoch3及group12，读取实际窗口2disable回执；先审批并fence事件入口(group13)，再审批shrink(group14)，保留历史回执；必须源停、事件全禁用。
2. 沿现有RuntimeDisableService禁用G并等待三个资源真实释放，正式disable/detach旧九入口，不删unknown或历史。核对实际CAS及detach回执后才进入后继安装。
3. 旧Host完全退出后，加载794612aa及后续代码；保持相同19包签名根，恢复H安装（同core1.4/growth1.10/niushop1.23/operations1.2），保留G历史，不改旧lock/generation/epoch。
4. 新H身份只能来自真实create结果；后续prepare/verify/stage/configure/enable、注册、exact切换全部按既有服务推进。继承既有业务Case及模型依赖后继，不重做业务历史。
5. 刷新真实健康及当前能力readiness，建立新当前数据窗口，自然触发时从安全诊断取得具体失败位置，针对性修复，禁止猜测patch。
6. 留证据并继续经营首链与八工作台；整个恢复过程不等于业务完成。

先测试固定身份、已有intent不重发；每阶段独立证据与CAS。任何未决调用先只读核对，绝不清理历史绕过排空。
