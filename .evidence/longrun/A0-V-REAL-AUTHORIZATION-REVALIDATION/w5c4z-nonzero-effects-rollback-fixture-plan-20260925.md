# W5c4z 非零 effects 与事务回滚隔离 fixture 方案（2026-09-25）

上位 231 A0-V/231-9 BG-00；W5c4y `4283cade` 已证正式 SQL 零 effects fixture 成功/重放，但真实原组是非零 effects，且严格 24h 尚未到。本波仅在可销毁隔离 PostgreSQL 补合同覆盖，真实组只读。

## 文件级九步

1. 复习 `a0v_091` 正式 SQL、原 group claim/input/member Owner 或 fixture、W5c4y 原测试及 231 权限/回滚边界。
2. 文件清单：本方案；优先新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c4z_nonzero_effects_pg.py`（必要时复用 W5c4y helper，仅最小修改测试文件）；本 verification。生产 Owner/迁移原则上不改，若发现真合同缺陷须先修订方案。
3. 用原正式 Owner 或已有可信 fixture，在隔离组留下至少一种可证明的非零 effect（优先 group claim/input/member，而非读取商城源行）；以原 `a0v_091` 关闭后核对 receipt 的 effectEvidence 与原 effect 行均仍存在且业务未接受。
4. 在同隔离环境制造更新中途可控 SQL 失败，证明 receipt 与 12 Run 终态同事务回滚、可再次唯一成功；禁止为测试放松真实角色或修改生产函数。若安全可控失败点不存在，记录缺口，不伪造覆盖。
5. 定向测试后跑 W5c3/W5c4 有界累计回归；隔离测试数据库结束后停用。
6. 浏览器只读核计划页/整组入口，不点击保存、运行或队列冲刷；不能从 UI 推断后端权限门。
7. 方案/代码一致性复审：fixture effects 必须与真实组效果类别可比，其他未覆盖效果显式保留；真实组仍需 DB-clock 严格 24h 与新鲜全门禁。
8. verification 落盘提交后 CAS 同步 docs/AOS 项目开发上下文和 Prime 独立受管记忆，读回状态。
9. 下一波 W5c5a：若严格 24h 未到，继续只读诊断/测试债；到线后先独立真实关闭方案与只读全门禁，唯一原 Owner 动作→核验→正式定义退休→direct successor。未知结果冻结不重发。

不可越界：m1 单写、不 push；不读取商城源数据；230 L0 挂起；旧 attempt 不补跑；dev-org/dev-project 仅零 canary。
