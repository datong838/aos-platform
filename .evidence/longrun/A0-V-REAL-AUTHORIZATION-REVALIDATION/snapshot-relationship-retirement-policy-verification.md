### SC4-5h6 显式清退策略候选验证

关系策略v2增加固定present-rows-only retirement约束：引用完整、拒绝晚于观察关系、禁止缺行删除；v1 retirement_mode默认disabled，原候选生成行为不变，模式纳入原完整hash且assess重新编译核对。当前PolicyOwner继续exact artifact/current release/public fields检查，v2不绕过原资格。

56项策略/Owner单测通过4.97秒；原关系执行+残留核验15项隔离PG回归通过77.48秒。新策略本身不生成tombstone。候选1.17.0相对1.16.0仅版本/策略/evals三文件变化，12映射逐字不变；静态14canonical关系、公开字段、缺客户/软删除可见性通过。对象mapping旧评估明确继承未重跑，不宣称新12类真实应用。

候选tree sha256:9cb8cd7c54fee2dd1f9e490b0d9f6e735045002f4b5d3164d6c1cd7ce83f89d3，policy sha256:03cd5157f54ed2c7156d82bf4903cff96c2c83459ce3e91b4637cdf59ee86ae6。未重建OCI镜像/签名/发布/安装，未删除真实关系。AR2扫描1923/187/93五类错误为空。

下一波：原Store增加显式tombstone的旧payload前置校验，必须在同事务持有端点/关系锁时比较准备时hash，避免清退覆盖期间更新；原Receipt成功重放校验自己的当前tombstone不再要求旧hash。随后在v2当前包策略门内固定残留清退命令、提交确认、原严格应用及精确投影。32+1客户引用缺口、正式Readiness/Fulfillment、真实首链和八场景仍待完成。
