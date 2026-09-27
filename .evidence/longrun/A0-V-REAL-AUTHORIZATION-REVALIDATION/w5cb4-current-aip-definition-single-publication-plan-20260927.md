# W5CB4 当前 AIP 定义单次正式发布波计划（2026-09-27，执行前）

## 范围和授权

- 承接 `f68b0ca9` 受控写入器、`366e96c4` 只读行门及 `833ac36d` signed exact 前置。此波只向 `aos_current_preview_20260927@a0v_106` 的公共 AIP 定义 Owner 写入当前 signed growth 1.11.0 的 10 Capability、6 Agent、37 Skill；不创建租户实例、Skill/CapabilityBinding、Runtime binding，不启自然 worker/Runtime Host、模型或外部动作。用户已授予本地开发和当前实例实操权限；预算/外部/发布 release 仍另门。

## 第 1–9 步

1. 复习 231 A0-V/A1、产品方案 9.3、当前强一致记忆与本波计划；精确读 HEAD、m1、工作树，原有脏测试/两个 test-only 文件只保护不提交。
2. 当前库独立只读确认三表及 Runtime binding=0，唯一 installation approved、四包 published、a0v_106；signed Receipt/TrustRoot/Registry contentHash exact；8080/8434 安全可读，18181 无监听，自然 worker/Cron 未开。
3. 固定**一个** canonical UUID intent：`55f1cce8-73a3-43b6-a834-b25c675d3afc`，记录在 verification，绝不在失败后换 id。先执行脚本默认只读，确认 EMPTY、intentExists=false、writes=0。
4. 命令级故障注入/隔离测试只针对 O_EXCL 重复、部分行/签名漂移/错误目标 DB/写后 hash 失配；如测试基础设施尚不能覆盖某门，则保留未验收，不假称全部绿。
5. 仅在 1–4 通过后，运行一次 `a0v_current_aip_definition_publish.py --execute --intent-id <固定值>`；命令未知/超时不得重发。若 SAFE_BLOCKED，保留 intent，独立只读三表和日志定界并进入正式恢复方案。
6. 若返回 EXACT，独立只读逐行核 6/37/10 及 source/hash、intent 内容、Runtime binding=0；绝不只信脚本 stdout。
7. 当前 8080 原进程不自动重启；若要看新六角色投影，依安全预览启停复核 Cron=false、所有 worker=false、第二 Host=0，再浏览器读回“定义可见但未绑定/未 ready”，八项配置仍缺。
8. 专项/累计回归、方案/代码一致性复审、风险登记；不把定义发布计为首链成功。
9. verification 落盘、m1 commit、同步 227/228 上下文，自动进入 BG-00 六角色合法实例/配置/绑定的下一波。

停止：任一签名/库/目标/intent/端口/Host/worker 漂移、未知写边界或部分提交，冻结而不重发；不读商城源、不回旧卷、不碰原 12 Run。
