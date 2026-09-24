# W5c5a 剩余 effects fixture 可行性与真实关闭预检方案（2026-09-25）

上位 231 A0-V/231-9 BG-00；W5c4z 已证 group/source claim 非零保留及中途失败原子回滚。真实 group 仍严格未满 24h。本波先判断能否不读取商城源数据、不提交真实 group 的前提下，在隔离库增加 group input/ingress command 及其正式 receipt 计数；不为追求绿灯虚构不满足源合同的行。

## 文件级九步

1. 复习 `a0v_045` group journal、`a0v_091` effectEvidence、native input fixture、231 A0-V 与原真实关闭停止条件。
2. 文件清单：本方案；优先在 `services/aos-api/tests/extension_runtime/test_a0v_w5c4z_nonzero_effects_pg.py` 参数化现有隔离 fixture，加一个无源空观察变体；若原合同不允许，则只新增本波只读诊断/verification。生产 Owner/迁移不改。
3. 优先复用隔离库原受控 ingress Journal 的合法 **empty observation**（不触碰商城或合成源读取）为同一 12 Run 保存 ingress command，并构造符合原 journal 约束的 group input；若必须跨不可逆提交或会导致真实源副作用，停止这条测试路径并记录缺口。
4. 专项验证 Receipt 的相应 effectEvidence 非零且历史行不变；失败要区分环境/fixture 与生产缺陷，不能直接改生产 SQL 绕过门。
5. 跑 W5c3/W5c4/W5c5a 有界累计回归，隔离测试库停用；中止的更宽慢集不算 GREEN。
6. 浏览器只读验收 12 计划与整组入口，页面不可代替 DB 独立证据。
7. 实时只读核严格 DB 24h、原 12 Run、定义禁用、Receipt/副作用与第二 Host；未到线维持 `automaticAction=false`。方案代码复审明确哪些 effects 未测。
8. verification 先落盘提交，再 CAS 同步 docs/AOS 项目开发上下文与 Prime 独立受管记忆，读回。
9. 下一波 W5c5b：继续可验证的剩余合同/内存债；真实组到线后另起独立方案、全门禁新鲜核对、唯一原 Owner 动作、独立审计及正式退休。

m1 单写不 push；不读取商城源行；旧 attempt 不补跑；dev-org/dev-project 零 canary；230 L0 挂起。未知提交边界冻结。
