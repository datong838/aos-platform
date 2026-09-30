# W5CB4 BG00do｜签名 BI 模板启动合同复核证据

| 只读检查 | 命令/来源 | 退出码与结果 |
| --- | --- | --- |
| 新 signed artifact | `psql` 查询 BG00dm 克隆 `asset_bundle_artifact` 精确路径 | 0；`bundle://a0v-growth-112/solution.ecommerce.growth/1.12.0/content/responsibility-templates/business-investigation.readonly.json`，digest `sha256:76036401433342f95328c43ecbcb618deb3c6adba335532b6bfc11af896d0f3b` |
| 本地静态生产入口 | `resolve_responsibility_template(TenantScope('org-org','dev-project'), published_template_ref('ecommerce.business-investigation.readonly'))` | 0；返回 true；函数源为本地 `_TEMPLATE_DEFINITIONS` 特判，没有查询签名安装 |
| 克隆签名 exact ref | `InstalledProductionProfileResolver(..., release_root=新 signed tree).resolve(scope, ExactRevisionRef(...上述 artifactRef, revision=3, contentHash=760364…d0f3b))` | 0；返回 false；克隆新安装 approved@3、active_revision NULL，`_fetch_rows` 只 JOIN active_revision |
| 别名与规范 URI | 构造已 active/签名/lock 其它字段全部满足的行，仅将 artifactRef 保留新 Registry 持久别名，调用 `_row_matches` | 0；返回 false；代码要求 `bundle://aos/solution.ecommerce.growth@1.12.0/` 前缀 |

`aip_responsibility_template_authority.py` 的 `published_template_ref` 注释已写“compatibility tooling only / Production resolution no longer trusts local definition”，但文件末 `resolve_responsibility_template` BI 特判与 `ecommerce_business_investigation_aip_authority.py` 请求构造仍走该静态 hash，和注释、签名来源要求不自洽。现有部分测试也断言该静态 true，所以不能只改一行后声称修复。BG00dp 的合同先区分配置准备态与业务 active，要求精确签名来源，避免打破其他模板正常路径。当前库无写，克隆未新增 Plan/Host/业务执行；本波没有代码修改，RED/回归留下一波。
