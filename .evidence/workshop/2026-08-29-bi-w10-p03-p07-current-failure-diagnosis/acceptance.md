# BI-W10 P03/P07 当前失败诊断

- 诊断时间：2026-08-29T10:15:57+08:00
- 代码基线：`aos-platform/m1@e4fedb32`
- API owner：PID 93117，启动于 2026-08-29T09:33:24+08:00
- 边界：仅读取最新自然 run 与已经脱敏的 DLQ 分类；未手工运行 Pipeline、未重放 DLQ、未输出源 payload 或凭据。

## 时间线与结论

| Pipeline | 最新自然失败 | 稳定分类 | 对应修复提交 | 修复提交时间 | 当前 owner 是否加载 |
| --- | --- | --- | --- | --- | --- |
| P03 ProductSku | 2026-08-29T04:00:00.883024+08:00 | SSH tunnel 未就绪 | `a5e42ccc` 有界握手与 managed 预建 | 04:41:54+08:00 | 是 |
| P07 Shipment | 2026-08-29T08:00:02.671566+08:00 | 缓存转发上的 MySQL query lost connection | `29013ba6` exact tunnel 端到端失败驱逐 | 08:15:37+08:00 | 是 |

两条失败均早于各自精确修复，当前 09:33 owner 同时包含两项修复。旧 run 不能证明当前实现仍有缺陷；也不能被改判为成功。当前 source/projection 仍分别为 ProductSku `62/62`、Shipment `19/19`，只证明旧投影守恒，不替代新自然运行。

## 专项验证

JDBC/SSH、P03、P07、Cron 与 SourceReadiness 合同共 `71/71` 通过；包含有界 SSH 握手、managed 预建、DB 建连失败驱逐 exact tunnel、并发 replacement 保护、P03/P07 映射及 fail-closed 路径。

## 后续边界

无需重复修改已闭合的同一代码路径。P03/P07 readiness 只能由下一自然 run 重新裁决；等待期间继续不依赖 12/12 的八菜单正式来源—页面—功能追溯，发现新的确定性缺陷再当场修复。BI-W10-02、Provider、外部效果与发布仍未获授权。
