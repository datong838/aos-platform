# W5c3l 第三个继任者自然 Configure 方案（2026-09-24）

## 目标

W5c3kR `099e9947`：安装 `407059df-6f1f-4927-acd7-8e388692838e` active/etag5，binding generation `7571af17-e2bb-4437-9f04-75812bae56c0` rev1/epoch1 disabled/fenced/ready，当前四来源配置 `f8d1f58f-9a49-48e2-b1a4-262e22f929f0` rev1/hash `sha256:f21169b03b4aba5dec2e6bbaa8ee8921e5ed833eee558f051b6e564aa068e359` 已 Stage；Host PID17302 Job/三资源 held。本波仅 configure，不 enable、不切九路/调度/业务 Run。

## 串行步骤

1. 只读再核精确安装/绑定/Host/Job/三资源、Stage 配置 ref/hash/payload 与当前四来源预算、九路9/9 legacy/fenced、12 schedule off、attempt/canary0；新 configure key Command/runtime operation0。
2. 新 `scripts/a0v_w5c3l_natural_configure.py` 与测试，0600 intent/result、新键 `a0v-w5c3l-third-successor-configure-20260924-v1`，原 `RuntimeConfigurationService.request(kind=configure)` 一次 CAS etag5/binding rev1/精确 configRef；自然 Host 消费。
3. 每50秒只读到 operation 正式终态；成功独立核 installation 当前 etag、binding rev/epoch/desired disabled/enabled false/fence true/configRef 精确、Host 同 PID/Job、三资源 held、业务计数不变。失败/未知冻结。
4. verification 与 m1 commit；下一波才单次 enable。九路与12调度继续关闭。

## 停止条件

Job/lease/四来源/预算漂移、operation 未终态或失败、原 Owner 拒绝、任何业务效应，冻结不重发。
