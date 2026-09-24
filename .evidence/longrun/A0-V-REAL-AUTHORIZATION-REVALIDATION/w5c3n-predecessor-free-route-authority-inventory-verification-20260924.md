# W5c3n Predecessor-free 路由权威只读清点验证（2026-09-24）

## 结论

**只读清点 GREEN；注册/切换仍未获正式路径。** W5c3m 启用后的独立 audit 仍为 `W5C3M_ENABLED_LIVE_GREEN`，安装 `407059df-6f1f-4927-acd7-8e388692838e` rev4/epoch3，Host PID17302，12 调度 off、canary0。九路 `6a402d31-83ad-546c-807f-508c87498ce1` 均 legacy/fenced、route rev338/group rev365、无安装/代际/epoch。

## 现行与历史权威

- 原 first-registration Receipt 只有一个，属于旧安装 `1c08edfb-ec0d-4abb-a411-7b6ec0d6066a`；现行 group 已有九路。`a0v_027` 的 first 注册 SQL 明确拒绝九路已存在，`a0v_026` 的历史表还限制同 group 唯一。
- 历史 successor Receipt 111 个，最新仍属于已卸载 DS `c6812824-a0c3-4adc-9ebc-d56178ae135c`；新安装的 successor Receipt 为 0。
- 最新 DS detach Receipt `d64e1b84-bdf9-4d15-b740-16673fcd651a`、hash `sha256:85f803080a8d348da90040540c5cc1d3fef48bbee857db3598265eaf0a37dd9c`，lifecycle detached、disable succeeded，fenced group rev364，九路快照与现行 group rev365 一致；旧 DS 资源 unsafe0。但正式卸载使旧绑定 desired `uninstalled`/observed `stopped`；`a0v_056` successor SQL 要求旧绑定 `disabled`/`unknown`，故不可用旧 Owner 直接注册。新安装 composition predecessor null 不可伪造旧安装 active。
- 新安装 source selection 0、runtime control 0；旧 12 schedule 全 disabled。现有 definition head 为旧 DR rev3 disabled，另两个历史 head retired；新安装 definition 0。

## 核验与下一波

本波仅执行 `scripts/a0v_w5c3n_route_authority_inventory.py` 的 read-only transaction，查询路由、Receipt 身份与受控元数据；未读商城源 payload、未注册/切路由、未运行业务。脚本直接复用 W5c3m 的严格 live audit，`python -m py_compile` 与实际只读执行需在提交前再核。

下一波 W5c3o 先写方案并复习产品/技术契约，设计最小、独立的“已卸载前任且 detach 快照精确 → 现行 ready 新安装”的注册 Owner/SQL：保留 immutable 历史、不更改旧 `a0v_056` 语义；要求九路 rev365/fenced、DS 卸载/资源释放/零 in-flight、新安装签名/配置/Host/预算四来源当前、全新幂等键与正式 Receipt。先测试及只读 preflight，再另波真实注册；不得直接切路由、开 12 调度或手工 run_definition。若该路径与现有产品/技术方案矛盾，先修方案而非改门禁。
