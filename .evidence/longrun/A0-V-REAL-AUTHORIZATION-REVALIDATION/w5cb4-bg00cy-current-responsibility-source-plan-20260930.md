# W5CB4 BG00cy｜当前职责来源与状态机顺序核验方案

## 上位约束

- 231-3：安装 `approved→runtime-apply→applied→runtime-verify→active`，配置随后执行；只有 active 指针与当前 binding 等条件齐备才可能运行。
- 231-9：当前安装与正式配置必须经产品入口形成，脚本、历史签名制品或页面可点不等于业务验收。
- 本波只读核当前 `org-org/dev-project` 的安装头、精确签名模板、职责计划治理、AgentInstance 状态；不读商城源、不写当前库、不启 Host/worker/Provider。

## 文件级工作与判据

1. 读 `aip_responsibility_template_authority.py`、`aip_production_contract_store.py`、231-3/9；以只读事务核 `bundle_installation`、修订、模板 artifact、职责计划/档位治理/AgentInstance 的当前事实。
2. 用已签名 artifact 的精确 ref 调现有 resolver 的只读连接，区分“制品存在”和“当前 active 可用于正式职责计划”。记录退出码及结果，不手工创建计划或补造治理 Receipt。
3. 若阻断来自 runtime-verify 前状态，不放宽 resolver。下一施工先定位 Host 身份/assignment/Owner 可独立代码项及正式授权边界，再走自然安装状态机；当前配置来源准备只在 active 后正向验收。

本波为状态机与当前来源审计，不改服务端或前端逻辑；RED/代码回归不适用。审计证据和 D-waves 清单须精确提交并同步 AOS/Prime 上下文。
