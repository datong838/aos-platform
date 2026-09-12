# 首链内部用途证据包

2026-09-12T02:02:43Z，基线90e43a81。Owner 实际读取三项已发布 Skill r2 source_license=internal、发布租户和当前开发模型治理，记录用户持续开发授权。新入口仅唯一当前库/克隆，固定 aip.governance Task，非经营 Case/Run，未调用 Provider。

首次克隆治理任务正常完成，接收检查发现 TAOR 的固定 stepRunId/stepKey/payload 外层；证据包事实提取也无法消费该规范格式。先补方案，再对 ProductionContractStore 仅增加精确外层的一层读取，保留顶层旧格式、不解包任意结构。修复脚本内层事实核验后从同一任务恢复，未重建或覆盖 Evidence。Bundle.required_fact_ids 两项非空，coverage/freshness 均服务计算 complete/fresh。

新增14项来源/租户/版本/外层格式测试，原生产契约及工作台证据构建8项回归通过，总计22项。克隆正式运行后重放524表不变。主库记录 governance Task task-4e0a77a4cf61469f81e8、Run run-ad4f00a37bc44953b8ac、冻结Brief和EvidenceBundle。Bundle evidence-bundle-e4e1e551b83c4c8983d4 r1 hash00c4fe32420b3a7fd49c9d89cfe0dc217d19f9b359508251eb553673415e8da0。

主库重放227个AIP表计数不变，223个租户AIP表canary摘要与本波基线克隆一致。使用本轮已有完整before-firstchain-contract备份为恢复基线。AR2-7通过。新增正文事实解析已由本次独立进程读取新代码；常驻API/宿主未以此为由重启，后续整体服务验收仍需核实加载版本。

许可摘要只记录本软件内部用途与用户开发授权，不证明第三方商用许可、不授权外发。治理任务1，不计为真实经营首链；ProviderCalls=0、BusinessRuns=0。下一波构建受控CapabilityBinding/SkillBinding及经营参谋激活，继续职责/源配置/自然链和八工作台。
