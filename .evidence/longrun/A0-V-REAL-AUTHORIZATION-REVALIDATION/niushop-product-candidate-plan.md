# Niushop1.5 商品快照候选

2026-09-13，ce8cfe96；专用Lease A0V-NIUSHOP-PRODUCT-CANDIDATE-20260913。新scripts/prepare_niushop_product_candidate.py、新bundles/candidates/ecommerce/platform.ecommerce.niushop/1.5.0/。只从hash固定的1.4复制，禁止修改已签名目录/旧候选；目标存在即拒绝，不删除失败目标，复查后按新版本处置。

仅改bundle版本、P02 mapping和静态eval。P01保持逐字相同，P03及其他图仍未激活。P02取site_id=1完整状态范围（不再is_delete=0/goods_state=1筛除），改明确snapshot；移除旧watermark cursor/soft_delete，使用v2源时间/删除/状态合同。goods_name→title、site_id→shopId、create_time→createdAt；其他来源字段保留。status目标显式status，0→INACTIVE/1→ACTIVE，is_delete=1→DELETED；枚举是固定方案候选，真实源出现其他状态则拒绝/待核，不猜测。

金额约束原非负price/market_price/cost_price必须保留。因此先补v2 validation.non_negative的显式列表支持（strict unique，所选int/decimal子集，坏声明拒绝），原v1 required-only不变；v2已存在无non_negative声明的合同兼容为空，不默认施加业务约束。测试负金额整体拒绝/数值0合法/文本字段不可当数值约束。

静态评估读取候选mapping/schema/masking，通过derive/compile/materialize、canonical对象、重复观察、上下架/删除、金额约束、来源额外列/错租户店铺/重复key拒绝。测试资料全部synthetic，明确不是实际商品行情。候选创建前对内存改后mapping先评估，通过后才复制；复制后评估hash与允许changedFiles精确一致。旧源hash执行前后相同；pending eval不得冒充通过。

后续另波：实际元数据核对、候选镜像构建与隔离资格、append-only Registry successor、当前installation受控升级、P02图/审批/一次真实读取。当前本波无SourceRead/RegistryPublish/安装副作用，不因静态评估通过自动跳过后续门。
