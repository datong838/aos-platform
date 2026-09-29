# W5CB4 BG-00p｜正式 Eval Judge/Target 执行权威只读审计方案

## 上位约束与目标

231 首链要求真实来源、自然执行、可复验产物；228 G2 要求内容事实性与渠道适配 Eval。AIP-4 E1B 的 Runner 只承诺精确引用、哈希与不可变 Report；它没有承诺注入的 Python 回调已经是正式 Judge/Target 执行身份。BG-00o 隔离 MinIO 因 Docker Hub 超时未完成，不能用样例对象填充 D01。

本波只读定位正式 Eval Run 前缺少的身份、租户、版本、签名、撤销与执行回执权威；核对当前库表、Runner 入口、Registry、发布门与产品方案。不得改代码、当前库或现有测试，不运行 Eval，不启动 Host/worker/Provider，不读取商城源。结论要区分现有精确引用校验与尚未证明的执行来源。

## 文件级输出和判据

- 本方案与 `w5cb4-bg00p-formal-eval-executor-audit-verification-20260929.md`：逐项列出可复核命令、退出码、现有保护与缺口。
- 后续最小实现清单精确到 `services/aos-api/aos_api/aip_eval_runner.py`、既有权威 Store/Registry、相关测试及必要迁移；在正式身份来源可识别之前先做隔离负向门，不能以调用者注入回调或测试夹具充作生产 Judge。
- 当前数据库维持只读。若需要新增正式身份表或迁移，必须作为独立波，在一致备份、克隆全链演练和零执行窗口后处理，不能在本波更新当前实例。

读回标准：今天最新 m1、当前卷/迁移/签名 Receipt 与 API/Web 健康可再核；BG-00p 只产生审计与下一波可执行范围，不声称 Eval、发布、自然首链通过。
