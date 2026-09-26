# W5ca8｜A0-V 当前风险登记的已被后续证据覆盖项清理方案

## 上位、范围与停止线

复习 231 A0-V→A1、230 L0 挂起、W5ca3 当前 18181、W5ca4/5 原组 no-authority、W5ca6 `next_steps` 去过期、W5ca7 隔离租约进程补证。AOS-000722 `incomplete` 仍混有 W5c8h–W5ca2 当时正确、但被 W5ca3/W5c9f–z/W5ca4/7 更新的现状语句（例如“18181 离线”“count 未知”“恶意自洽未测”“文档后置项未隐藏”）。本波只校准**当前风险导航**，不抹掉历史 verification/events，也不改变业务权威。

## 文件级与删除准则

- 只读：`docs/palantier/AOS项目开发上下文/memory/authority.json` 的 `incomplete` 尾段、W5c8o/q/r、W5c9f/g/j/l/o/p/z、W5ca3/4/5/7 verification，现场 18181/8080/原十二 Run 只读必要事实。
- 先在 audit 逐类列出“原语句→后续证据→保留的真实风险”。只删除被后续提交或当前只读事实直接反证、并已由较新风险项覆盖的条目；`a0v_095–098` 真实未迁、全机 Fleet/旧入口撤权、原始行独立语义、原十二 Run、业务 8080、租约真实到期未发生等必须保留。W5c7 早期未闭测试债和不确定项不在本波清理范围。
- 变更：仅 `scripts/memory/memoryctl.py authority-update` expected-revision CAS 替换完整 `incomplete` 数组，其余 fields 保留；自动投影文件 `docs/palantier/AOS项目开发上下文/memory/{authority.json,events/2026-09-26.jsonl,projections/aos-project.json}`、`01-当前项目状态.md`、`06-当前执行检查点.md`；补 D-waves、上下文 154、Prime 同步。不得手改生成投影、不得触碰生产代码/DB/Host。
- 验收：每个删项都有具体 superseding verification；无旧“18181 离线/新代码未加载/恶意自洽未测/已修文档仍未修”当前风险；原组硬门、真实迁移、8080 离线与实际租约到期待验仍在；CAS/`memory-validate` GREEN、Prime CURRENT、精确提交。若缺后续证据，保留该条；CAS 冲突冻结不覆盖。

## 九步

1. 上位复习；2. 本方案先提交；3. 逐项静态审计与当前只读状态；4. 最小 CAS；5. JSON 专项/累计投影校验；6. 8080 业务浏览器不可验收、18181 文档只读；7. 方案/风险保留一致性复审；8. audit/verification、D-waves/上下文/Prime、提交；9. 自动下一波。

商城源不读，230 L0 挂起，dev-org 仅零 canary，原组 ACK/closure/replay 和真实迁移禁止，m1 单写不 push。
