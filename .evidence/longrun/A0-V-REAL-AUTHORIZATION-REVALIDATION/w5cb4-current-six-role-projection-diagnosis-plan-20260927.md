# W5CB4 当前六角色投影差异诊断波（2026-09-27，只读方案）

## 目标与上位

- 承接 BG-00 当前新库安装与 231-9 六数字同事同一 Task/AgentInstance 的原则。页面现报 `ecommerce agent definitions differ from 6-role authority`；本波只确定故障属于缺定义、版本漂移还是代码错误，不写当前库。
- 复核当前 m1、现有签名安装和新库 schema，检查 `AipOperationalProjectionStrip` → `/v1/aip/operational-projection` → `AipEcommerceAgentInstaller._definitions`；只读统计 AgentTemplate/SkillTemplate/CapabilityRevision 的当前行数和 source revision。对照当前已签名 `solution.ecommerce.growth` 包版本及发布器支持版本。

## 文件与验证

- 只读代码：`apps/web/src/components/aip/AipOperationalProjectionStrip.tsx`、`services/aos-api/aos_api/routers/phase3_aip_agents.py`、`aip_ecommerce_agent_installer.py`、`aip_solution_pack_publisher.py`。
- 只读库：仅 `aos_current_preview_20260927` 上三张正式定义表 COUNT，不访问商城源或旧卷。
- 若是空定义，保持页面报错/安装禁入，登记后续当前签名包来源与正式发布器兼容性修复；不运行硬编码旧版 publisher，不用 SQL 手填，不启 Runtime/Provider。verification 落盘并提交后进入下一波。
