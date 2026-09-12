# P02正式首读准备

2026-09-13 04:46，m1。API已由原12426优雅停止，新PID22015使用ee6c0aea和Niushop1.5签名根；/v1/health、/v1/ready、5173、8434均HTTP200，Host v16独立保持运行。Cron/自动模型任务/第二Host/源预热关闭。本地诊断数据库身份仍aos_app superuser/bypassrls，生产Web身份收敛未完成，不具备发布结论。

新增只读scripts/a0v_p02_current_preflight.py，从当前签名映射/schema/masking生成固定Product图并经过原Owner范围校验/快照编译。4项图范围测试通过（本次只读工具先实现后测试，无伪造RED记录）。实际mapping hash cba304c2…，28字段/ns_goods/Product，图及canonical pipeline均经正式HTTP登记200，读取源行0。图登记前404证据在工具输出，不把HTTP配置200当采集完成。

当前Owner preflight通过，draft绑定新安装active@5/epoch3/config f134da1e@1/source-config a84b6c79@1，graph revision1，15分钟窗口至20:58:42Z。使用既有admin本地开发token（仅内存）经正式SourceSelection/RuntimeControl接口审批，创建sch-p02-qyh-controlled-20260913-v1初始disabled并exact绑定。04:45:54Z独立runtime数据库回读：schedule唯一、disabled、P02引用正确，binding/control hashes与HTTP响应相符，当前control sourceclaim0。

计划限site_id1、最多1000行、30秒、一次源调用。尚未启用或执行Run，尚无Product真实数据证据。下一波单次正式Run，先核原Claim/Journal/Receipt和对象投影再判断成功；失败不换key重读。旧P01保持disabled，旧Receipt保留，未push。
