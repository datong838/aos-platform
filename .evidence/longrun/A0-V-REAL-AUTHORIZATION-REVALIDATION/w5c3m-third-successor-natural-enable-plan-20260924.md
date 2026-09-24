# W5c3m 第三个继任者自然 Enable 方案（2026-09-24）

## 目标与边界

W5c3l `af3b06d8`：安装 `407059df-6f1f-4927-acd7-8e388692838e` active/etag5，binding generation `7571af17-e2bb-4437-9f04-75812bae56c0` rev3/epoch2，configRef `f8d1f58f-9a49-48e2-b1a4-262e22f929f0` rev1/hash `sha256:f21169b03b4aba5dec2e6bbaa8ee8921e5ed833eee558f051b6e564aa068e359`，desired disabled/enabled false/fenced/observed unknown；Host PID17302 同 Job/三 held 资源。九路 legacy/fenced、12 schedule off。此波仅原 RuntimeConfigurationService 单次 enable，绝不切九路/调度或跑业务。

## 串行步骤

1. 只读核精确安装/binding/配置 Stage 与 configure 正式成功、四来源/预算当前、Host/Job/三 held 资源、九路9/9 legacy/fenced、12 schedule off、attempt/canary0，新 enable key Command/runtime operation0。
2. 新 `scripts/a0v_w5c3m_natural_enable.py` 与测试，0600 intent/result、键 `a0v-w5c3m-third-successor-enable-20260924-v1`，原 Owner `request(kind=enable)` 一次，CAS etag5/binding rev3/精确 configRef；Host 自然消费，不手工执行。
3. 每50秒只读至正式终态。成功独立核唯一 binding enabled=true/ready/fence=false、配置未漂移、Host 同 Job/三 held 资源、九路仍 legacy/fenced、12 schedule off、业务计数不变；失败/未知即冻结，不重发。
4. verification 文件、m1 commit。下一波才正式九路 route 注册/切换与12新 selection/control/definition，先方案。

## 停止条件

Host/lease/四来源/预算/路由/调度/canary漂移、operation不终态或失败、业务源读取/运行出现，立即停写并正式退休/direct successor。
