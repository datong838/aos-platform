# E17-s3o-w-ao-b30｜Capability CREATE 精确 published 目录来源验证

## 当前权威只读对账

- `m1@d525bc82` 开波、原库 `aos_current_preview_20260927@a0v_135`。`BEGIN READ ONLY`：`aip_capability_revision` 10条均 published，sourceRef 元数据均指 `SolutionPack/solution.ecommerce.growth/asset-registry/1.11.0`；Binding0、共享 Receipt6，runtime 对共享 Receipt INSERT=true。`.env` 所指 bundle root 存在，Growth 子目录仅 `1.11.0`；当前 `bundle_installation` 1条 current_revision3、active_revision NULL。这里只读目录元数据，没有读取商城源、没有重验签名；published Catalog 不等于 active 安装/Growth1.13/Host授权。

## 方案、RED、最小隔离修复

- 231-4/BIND-1 和原 `AipCapabilityBindingService.create` 复习后文件级方案先提交 `m1@83c7e11c`。只在 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 的 disposable full-schema DB 用原 `AipCapabilityRegistry.publish` 造一条 published、一条 evaluated 的 test-only CapabilityRevision；独立 issuer 仅授 catalog SELECT、Binding写与原精确租户策略，真实登录的 `session_user=current_user=issuer`。
- 新负例为空 ref、evaluated ref、错 hash/版本/ID/assetType 的直写 Binding＋create Receipt。目标单项原 exit1、`1 failed`，`Failed: DID NOT RAISE InsufficientPrivilege`。测试还核 issuer catalog INSERT=false，直接 `ALTER TABLE aip_capability_binding DISABLE TRIGGER ALL` 被拒；权限在 finally 精确撤销。
- 最小只改 test-only BEFORE INSERT marker：要求 `assetType/assetId/revision/contentHash` 四键精确、revision数字且正整数、hash格式正确，并用 issuer 的只读 catalog 权限查询精确 id/revision/hash 且 lifecycle=published；缺失抛42501。原 CREATE 初态、UPDATE列形状、同版本一一 Receipt 与普通合法 operation 保持。

## 验证与限制

- 目标单项 exit0，`1 passed, 1 deselected`；五文件相邻 `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_e17_s3owaob12_tool_receipt_identity_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_aip6_003_exact_instance.py tests/aip/test_aip6_capability_run_handoff.py -k 'not downgrade'` exit0，`14 passed, 1 deselected, 1 xfailed`。旧 xfail 是生产共享 Receipt operation 门缺口，旧降级测试因135禁令排除。`py_compile`/`git diff --check` exit0。
- 原库后读135/Binding0/Receipt6，未写；未新增生产迁移、正式角色/私有凭据/API或运行逻辑，不重启。Catalog fixture 是 test-only 发布行，不证明当前签名 Growth1.13、active Installation、OIDC 或六 Binding。正式 issuer 仍可用任意已发布 catalog 行直写，Receipt 的 resourceRef 未与 Catalog id 强绑定，受控命令来源与当前安装一致性尚未封。下一波应优先核正式安装/发行链和 Receipt exact source，再考虑 `a0v_136` 与当前库安全切换。
