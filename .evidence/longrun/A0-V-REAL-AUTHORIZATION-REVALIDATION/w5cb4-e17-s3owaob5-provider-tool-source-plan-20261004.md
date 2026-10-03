# E17-s3o-w-ao-b5｜正式 Provider 与 Tool 来源最小核验方案

## 上位复习

231 主计划、AIP-7 22 与 BIND-1 31 要求 Provider `secretRef+version`、健康/Eval/预算/容量和精确签名 ToolDefinition/RegistryReceipt 来源；不能从 dev-org 或旧可变目录补成当前权威。b4 当前正式 Reader/issuer/OIDC/Host 缺口只阻原实例切换，不能停长期研发。

## 文件级步骤

1. 只读核 `aip_network_issuer_config.py`、Provider/Tool 原发行入口与当前签名 bundle/Receipt 清单，优先定位已登记的正式来源或可独立修复的代码缺口。读取签名制品及项目元数据，不读商城业务源数据/凭据明文。
2. 两个候选逐项列出当前证据、已有授权、缺的外部来源与独立可做事项。若找到可修代码点，先补精确 RED，再最小实现、专项和相邻回归；否则只封闭相关实例，转下一已登记安全研发切片。
3. 当前真库只读；不启动 Host/worker/Provider，不手工 Run、不重放旧12 Run、不碰230 L0。未证实的外部 Provider 或 Tool 来源不得造假。适用时再做浏览器验收。
4. 方案/代码复审、verification、m1 精确提交、D-wave 与 AOS/Prime 上下文同步后继续下一波。
