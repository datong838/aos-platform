# D01 描述性方法适用性与输入缺口

2026-09-11，基线68d1f556，AOS-000573。复核技术15、160、MethodRevision与MetricValue最小合同。已有Query绑定/证据生产不等于数据质量权威或完整指标ready。

新增 `services/aos-api/aos_api/ecommerce_analyst_portrait_method.py` 纯检查：接收上一层已从Owner读取的方法、指标定义、查询结果、scope/共同cutoff/now。重验方法/定义完整hash和类型，指标唯一，查询同scope/metric/complete，最小来源数按不同exact原始source去重；拒绝相同来源ID多版本冲突。用每一个原始source.cutoff而非查询创建时间检查方法最大时效，禁止用重复指标把来源数凑够。Query自身cutoff必须同frozen cutoff。不读取默认DB、不调用模型、不产出MetricValue或整体ready；独立质量权威仍必须检查。

新增 `services/aos-api/tests/test_ecommerce_analyst_portrait_method.py`：源去重不足、同源版本冲突、过期/未知源、未来cutoff、错scope/指标/方法hash/空清册及边界秒检查。现有方法/来源模块回归。

已识别的后续真实路径依赖：QualityEvidenceStore当前仅存储及重算测量，代码内无实际生产调用，不能拿它存在当质量计算已接通；CanonicalPopulationReader最多99个完整对象，真实聚合不可截前99条；QueryEvidenceProducer当前仅接受Evidence来源，不支持Dataset指针。必须补固定业务聚合及来源/质量证明，再D01生成与宿主真实执行，不隐性放宽这些条件。

并行只读恢复核查（仍单写者）：本机SSH agent空，既有密钥经apple钥匙串成功加载；认证条件变化后只重试一次既有服务器，仍Permission denied，未建隧道/读业务数据。无密码/私钥输出，不再重复相同认证。本波证据单独记录。

退出：先失败测试、最小实现、自测/既有回归、缺口清单/接续/哈希/提交。下一波固定业务聚合与完整指标质量来源，继续D01可信画像；真实数据恢复仍依赖服务器接受的既有SSH身份。无主库业务写入/Provider，不push，230 L0挂起。
