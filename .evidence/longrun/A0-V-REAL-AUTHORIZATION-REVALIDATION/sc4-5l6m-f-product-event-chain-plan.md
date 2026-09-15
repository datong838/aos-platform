# F商品事件经营首链接续方案

Rules：m1单写、真实来源与当前权限、通过产品Owner/Service配置，不直接改业务表，不push，230 L0挂起。目标是实际更新触发Case/Run及后续产物，不以预检或入口通畅代替业务完成。

现状：F 1.9已真实恢复九入口，binding6/epoch3/group5。旧E商品图及源配置可复用，但安装绑定、审批、控制与事件Policy不能冒充F配置。先通过F当前签名根及真实resume收据只读验证现有P02图、Mapping/Schema/Masking、niushop源引用，再形成F专属selection/control草案。

新增scripts/a0v_growth19_product_preflight.py及专项测试：隔离加载原Product预检算法，固定F create路径、1.9根、F resume路径；复用原require_current_head全字段校验并增加F固定ID/代次/配置限制。原require_cutover_resume增加expected_outcome关键字且默认旧E不变，新F传明确标签，保留当前收据hash、数据库历史、operation/epoch/revision/claimPaused校验。原E执行器行为不改。

后续：selection→runtime control→schedule binding按正式Service，15分钟窗口按实际每轮重新形成并审批，不伪造过期授权；选择既有真实Case或新业务计划时先核实其目标、素材、来源，Policy精确绑定F。新增event_dispatch ActionType及AIP审批后走a0v054 expand，只有再经event_control独立审批才能开启自动事件任务。未知结果保留并只读回查。最终验收必须包括真实数据来源、自然触发、可读产物及人工评审续跑；外部发送/发布不包含在本波。
