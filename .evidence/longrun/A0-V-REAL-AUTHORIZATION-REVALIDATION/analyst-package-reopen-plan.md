# 新增分析闭包回开方案

基线 m1@9bab3171，2026-09-11。依据231-1四层合同与AR2 closure-manifest固定点规则。继续既有全权串行开发；不push，不改主库，不注册新运行入口。

## 问题与范围

ar2-7扫描1757模块出现23个未分类反向调用方。新增D01/D02/D03和阶段评审包含领域规则与宿主事务混合，旧AR2 fixture完成不能覆盖这些增量。需要检查全部ecommerce_analyst模块，而非只消除23条报错。

## 本波文件与步骤

1. 本方案先行；保持历史preHash。
2. .evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/analyst-package-inventory.json：逐文件实际SHA、直接依赖、目标、拆分责任与PENDING状态。
3. .evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md追加接续登记；不改历史完成含义。
4. 重跑原verify_closure.py，新增节点继续展开；不放宽验证器、不把平台私有Store复制到包。
5. 验证清册与文件对应、hash、状态、目标和依赖方向，记录尚未迁移。
6. 证据提交与两份接续文档更新；下一波先拆纯解析/业务契约，再通过SDK连接受控宿主能力。

## 后继实施与退出门

纯业务解析/提示词/领域状态规则归growth；通用Task、AgentRun、Eval、Artifact、身份和不可变事务能力仍由宿主拥有。现有混合Receiver/Service/Worker必须拆为包内编排和事务SDK适配，不允许直接把整个文件宣称公共port。领域DTO需包内版本合同，平台兼容不得import bundle。写端口必须在提交事务内复核DispatchRef及安装/epoch/fence；仅Python类调用测试不能授予安装执行权。

目标文件不存在或内容尚未拆分时必须PENDING；闭包分类通过只说明枚举已登记，不能关闭可插拔验收。后继还需独立构建、禁止aos_api导入、旧路径无旁路、停用/卸载/重装及完整真实首链验收。

本波不改生产Python，无新运行逻辑；风险是分类遗漏或把计划误报完成。用全量逐文件hash及显式未迁移状态控制。回滚只撤销本波清册增量，不触碰用户文件或历史证据。
