# W8-08 生命周期与旧路由退役工程证据

- 代码提交：`8e33ed9e58bd15be5041a626b919a381bb4128de`
- 正向租户合同：`org-org/dev-project`；`dev-org/dev-project` 仅用于负向隔离测试。
- 前端专项：3 files / 24 tests GREEN。
- Web 累计：243 files / 2207 tests GREEN。
- 后端 Installation 专项：10 tests GREEN；覆盖 exact replacement、leaf-first rollback、terminal uninstall、append-only history 与 tenant isolation。
- 生产构建：TypeScript + Vite GREEN，345 modules transformed。
- 内置浏览器：`/workshop/orders` 在正式 API 不可达、没有 active replacement/retirement Receipt 时保留旧只读入口；唯一 H1、唯一 main、无横向溢出，未观察到 uncaught error。
- 截图：`legacy-route-preserved.png`，SHA-256 `1eb678d0763e1f0656af3a20a9c48bfe3ac01341f0aea1ab67abcc2aedd2b9ee`。

本目录只证明工程合同和失败关闭行为。没有执行 publish/install/upgrade/rollback/uninstall、migration、真实路由切换或退役，也不构成外部副作用或发布授权。
