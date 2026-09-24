# W5c5h Host 排他权威缺口设计核验（2026-09-25）

上位 231 A0-V/231-9 BG-00；方案 `ef907c48` 先行，设计证据 `41f55136`。本波是设计/静态审计，不是租约实现或关闭授权；生产 Host/Owner/迁移零改。

## 九步证据

1. 复习 AR1-c 目录/Host selector、A0-V 真实运行边界、`a0v_091` 正式关闭门。
2. 文件仅本方案、新增 `w5c5h-host-exclusion-authority-design-20260925.md`、本 verification；没有代码或数据库变更。
3. 静态核对：`ar1_003` 只有配置 assignment/identity/历史，没有 live Host 租约；`PostgresRuntimeTenantDirectory` 只读 descriptor；当前启动器 `fcntl.flock` 是本机/共享文件路径排他。`extension_runtime_resource_lease` 是操作资源租约，不是 Host 存活租约。设计提出 additive DB 租约/epoch、Host opt-in、逐 worker 同事务 fencing、旧角色撤权及全机清单读回的分波合同，均标为**未实现**。
4. 专项 Host/目录/生产装配与 W5c5 邻接 **138 passed、11 skipped、7 warnings**。首次 5 个失败因 dotenv 注入已不存在的历史 `AOS_BUNDLE_ROOT=.../.aos-recovery-20260913/state`；仅测试进程设置 `AOS_DOTENV_DISABLED=1` 并移除该环境覆盖后重跑通过，未伪造目录或修改生产配置。
5. 累计 W5c3–W5c5g 与定义、attempt、lease、preparation **252 passed、7 warnings、31.96s**；隔离 `aos-dev-pg` 已停；`git diff --check` 通过。
6. 5174 浏览器只读见 12 单路计划、A0-V 整组 rev4 已停用；`BROWSER_PARTIAL`，页面不证明 Host 排他。未保存、运行或冲刷队列，临时页/前端已关闭。
7. 设计自洽但未完成：DB 租约表本身不能 fencing 旧进程/外部副作用，物理第二 Host=0 仍需全机清单和进程/容器读回。严格 24h、真实关闭/独立审计/退休/direct successor 未执行，A0-V/BG-00 未过；任何未知冻结。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5i：先复审当前迁移头/权限，在隔离 PG 实现 additive Host 租约基础和并发/fencing 合同；不启用生产 Host。

m1 单写不 push；旧 attempt 不补跑；230 L0 挂起；dev-org 零 canary；商城源行不读。
