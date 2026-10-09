# PRE_COMMIT 候选的后置回调原生反例

Rules：231、单写者、先方案后编码、独立 test-only 资源，不 push/正式库/Host/Provider。原严格提交完成截止不改写。

候选一可信结束协议：静态审计已发现 callback LIFO 与后置等待，进一步实际验证，避免仅凭源码下结论。候选二 typed Model 全计划风险/唯一 Intent，依原批准父与真实输入，仍保持独立施工。当前选一。

精确新增本目录 probe.c、Dockerfile、register.py、create_lab.py、run_probe.py、verify_probe.py、checkpoint.json 与结果。新独立镜像只在现有精确 PG16.14/原 C verifier 镜像上添加 test-owned 回调库；新容器 aos-precommit-probe-20261009、新 local 命名卷同名-data、5442，768MiB 无 swap、256MiB shm、1CPU/128PID、SCRAM、耐久 on。保持全部已有容器身份/启动时间/挂载/端口及卷不变，不删除保留库或清统计。

实验函数仅管理员在新 lab 的 synthetic obligation 注册 deadline 和回调排序，无签名 Source、模型调用、真实预算或执行权限。两单次新尝试：check→wait 在检查时未过期、后置原生 pg_usleep 自然跨期且 COMMIT 成功；wait→check 跨期必须 23514 整笔回滚。以 actual xid/DB clock/已持久行/pg_xact_status 独立回读；不改系统时钟/期限、不重放旧实际 Source。预期首个候选硬截止 RED；这是回调机制反例，不冒称完整产品漏洞或安全门验收。

任意未知 build/run/COMMIT 先按 exact attempt 只读对账，不重发；所有步骤先记 intent/receipt。实验所有 SQL 与扩展安装只在新资源，未接默认 migration/服务。没有浏览器适用。

首轮 build 已明确 exit1：Dockerfile 的 FROM sha256 被当作远端名，而非本地镜像引用；没有 iidfile、容器、卷或秘密文件创建。修复为新自有 base tag，tag 精确绑定原不可变镜像 ID；另记 r2 intent，保留 r1 日志，不改任何旧镜像内容或 tag。
