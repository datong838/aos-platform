# W5CB4 E13：当前安装 Apply→Verify 正式激活计划（2026-09-28）

## 上位合同与现场身份

231/231-9 BG-00 要求真实包可安装、配置、禁入、恢复、卸载重装，安装与业务启用分离；栖月汇首链不可靠开发者手工接线。E12 读回当前唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`：revision 3、ETag 3、`approved`、active pointer 空，运行实例 `not_prepared`、无代次/绑定；正式源/管道/Selection 均 0。Registry 四包为 published，现有 evidence 最早过期 2036-01-01。浏览器 `/apollo/assets` 产品入口显示“执行 Apply”，原服务端在当前页有详情/时间线和幂等动作控制。当前卷 `aos_current_preview_20260927` `a0v_109`，命名卷 `aos-a0v-recovery-pg-data`；m1 `112fbdd5`，不 push。

本波只激活已批准的**安装指针**，不启 Runtime Host/worker、业务配置、真实来源或自动任务；`Apply` 的 dry-apply evidence 和 `Verify` 的 verification evidence 必须由原安装 Owner 当前事务产生。用户已授权唯一开发与当前实例实操；不把测试/页面绿当作结果。若 preflight、权限、签名、幂等、版本、结果回读任何一项不明，冻结该命令原键，停止后续写动作并仅只读对账；不得换键重试。

## 文件级与运行清单（先于动作）

- 本波先**不改代码**。复用 `services/aos-api/aos_api/asset_registry/installation_service.py` 的 `apply/verify` 及原 `_revalidator`、`installation_store.py` 的状态机、`apps/web/src/pages/s2/assetBundles/installationActionHooks.ts` 原键/未知结果保护。若发现生产缺陷，先补本文具体文件哈希和测试，再最小修复。
- 先用现有 `pg_dump` 对当前 `aos_current_preview_20260927` 做新的、只增不删的自包含备份（0600），记录体积/摘要；不能拿 E09 的 a0v108 备份覆盖现卷。只读查询安装指针、事件/命令行数、发布包/签名证据、tenant canary 与 Runtime Host/worker 0。
- 正式产品页选精确 installation ID，确认 `approved`、revision/ETag/Lock hash 与计划一致；一次点击 Apply 并完成原 UI 确认。返回不确定时不再点，按原键回执/服务端指针只读对账。明确看到 `applied` 与新增 `dry_apply` evidence 后才执行一次 Verify；明确看到 `active` 与 verification evidence/active pointer 后才宣布安装激活。
- 执行期间及后继续证明源/管道/Selection/Store Receipt 无新增、18181 关闭、Host/worker 0；活跃安装指针不等于业务调度已启用。隔离专项及累计安装/运行控制回归、浏览器验收产品安装/运行页面、方案/代码一致性复审、verification 落盘并提交。

## 串行 9 步与退出门

1. 复习上位产品/技术与 E12、当前唯一安装/包/权限/Runtime 状态；2. 冻结本文和当前卷备份/命令边界；3. 经产品入口执行 Apply 一次；4. 原键及状态独立读回、专项反证；5. 经产品入口执行 Verify 一次（仅在 Apply 确认后）；6. 累计回归与浏览器状态验收；7. 方案/代码/数据/越权风险复审；8. verification 落盘；9. 精确提交、上下文/Prime 更新、自动进入 E14 运行资源与配置产品路径。

停条件：安装非唯一、状态/ETag/签名证据漂移、备份失败、未知提交边界、服务端拒绝、业务来源/执行副作用非零时停止写动作并只读对账；正式退休/重试另立波，不在本波换键试。保留所有旧卷、备份和业务数据；不读取商城源、不手工 run_definition、不重发旧 12 Run，230 L0 挂起。每天用当天最新 m1 与原命名卷全面重启 DB/API/Web 并读回后继续 Loop。
