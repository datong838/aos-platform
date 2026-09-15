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

新增 scripts/a0v_ecommerce_diagnostic_reinstall.py：沿已验证event_complete_reinstall profile，只固定前序G及后继H独立目录/幂等标识；相同19签名包，不改旧脚本、旧版本、旧Receipt。H身份由create结果取得。测试固定G前序、generation及未知输出保护。

## 060结案后恢复原shrink
060正式部署成功，21项均经服务形成不可变未接收结案Receipt。新增scripts/a0v_g_shrink_after_closure.py，保留原失败shrink-intent：核对它与原批准request完全相同、当前仍group13、同idempotencyKey没有shrink Receipt、G不存在claimed/unknown、21结案完整且hash正确后，记录独立recovery-intent并调用原Lifecycle（仍复核当前审批）。如独立恢复意图已存在，不重发；若审批过期则另走正式新审批，不改旧回执。测试缺Receipt/残留unknown/漂移证明拒绝。

06:46原shrink恢复在审批检查处拒绝，未产生目标Receipt。只读核验原审批事件已于22:37Z到期，Proposal本身尚未到期；没有修改旧审批。新增scripts/a0v_g_retirement_approval_renewal.py：独立新request key、重新精确审批，要求旧key无Receipt、group13不变、21结案完成/无unknown，随后由原Lifecycle再核验当前审批并shrink。

## H事实与接线计划（06:53）
Host5448、API5449已加载诊断代码；原93538/93655正常退出。H安装1cc13337-c1de-40a7-b45e-acb41f20a19b，generation ba5d7266-5e7e-454f-85c0-04709305592f；lock sha256:b993a02c792ddd0dac0345243631f8a49aac0b6075e3b3ac71b1c504bb9e7bce，同19签名包；prepare/verify/configure已成功。配置e83b25ec-4c20-46b7-a686-b1bcec973b9f@1，hash sha256:316dffe386f4982d065bd3bb5956ec3dffcc856d1494349c8222cd3ca281b1ba。G detach Receipt 4cfd53a7-af4a-48ce-97e6-da45d86caf44。
新增scripts/a0v_diagnostic_successor_business.py，沿原G注册器固定H事实与Gdetach、group14；scripts/a0v_diagnostic_successor_cutover.py沿原exact审批/prepare/pause/commit/validate/resume，H独立keys/receipts，禁止重发未知。新增测试覆盖H身份/前序/组修订拒绝及未知intent。

06:55校正H注册计划：14是事件shrink后的组版本，后续正式disable fence到15、detach到16。原固定H注册器错误沿用14，被SQL拒绝且H注册Receipt=0；产品门禁正确。保留原register-intent，H registration-v2使用新key并固定真实post-detach group16，补测试防止把pre-disable版本用于后继注册。不是放宽注册条件或修改旧Receipt。

07:00 H启用runtime4/epoch3 ready；registration-v2 Receipt 85fd4c05-0729-4834-adf9-6cc17f475e57，sha256:f5e0d07df07adba05ca4d79629fa39cbc48ddb3fd09a82b7c16543050908ea99。正式cutover approve/prepare/pause/commit/validate/resume全部成功，新core组17；H注册/切换测试22通过。下一波当前r3能力/Skill健康刷新与H真实Product窗口，诊断Host已就绪。
