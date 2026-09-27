# W5CB4 当前六角色实例安装身份接续计划（2026-09-27，编码前）

## 上位与当前现场

- 231 A0-V/BG-00、栖月汇产品/技术方案要求数字同事实例复用公共 AgentInstance，不造第二身份表；未 ready 保持禁入。当前 signed 1.11.0 定义已在新库正式 6/37/10，浏览器 0/6 可自动执行、安装 `not_prepared`、Runtime binding=0。
- `AipEcommerceAgentInstaller._definitions()` 已单选当前完整来源，但 `install()` 回执 `solution_pack_version` 仍固定旧 `1.3.0`。此误标必须先修，不能拿错误版本回执安装六实例。另安装页登记服务 503 根因是安全预览没有受保护 `AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE`，不以普通 DB 身份冒充；该独立门留后续正式登记。

## 文件级最小改动与核验

1. `services/aos-api/aos_api/aip_ecommerce_agent_installer.py`：从已选中的六模板 `source_ref.revision` 精确决定回执 SolutionPack 版本；仅允许旧 1.2.0→1.3.0 和当前 1.11.0→1.11.0，混杂/未知 fail closed。六实例创建本身不在此编码子波自动调用。
2. `services/aos-api/tests/aip/test_aip_ecommerce_current_source_selection.py` 与现有旧测试：当前/旧版本、混杂/未知拒绝；专项加相邻累计，不依赖历史签名目录 API 夹具。
3. 当前库只读核六模板、0 AgentInstance、0 Skill/CapabilityBinding；浏览器只读仍 0/6，Runtime Host/worker=0。verification 落盘并 m1 commit。
4. 下一执行子波再用唯一 intent、当前租户 `org-org/dev-project`、正式 AIP Owner 建六个 `provisioning` 实例并逐行回读；任何未知结果不换键重发。Skill/CapabilityBinding、职责计划、预算和其他配置另门，绝不把实例安装计为可运行。
