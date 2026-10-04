# E17-s3o-w-ao-b35｜Catalog 与当前签名包内容重算检查点

## 上位方案与 RED

- 231-2/3、BIND-1、b34 方案复核：published Catalog 仅准 provisioning；就绪、激活和运行要当前签名安装、撤销、租户、代次、权限同源。b34 strict xfail 仍证明当前就绪门缺失，不以本波纯计算关闭。
- 原 `CurrentDefinitionSourceProof` 在发布后未与 Catalog 行同事务持久保存；`source_ref` 只有 SolutionPack id/version，无 bundle hash。原 `AipSolutionPackPublisher._publish` 的十项 `content_hash` 可从签名包内 Catalog/schema/policy 精确重算。先写 `test_current_capability_hashes_recompute_from_exact_candidate_without_publication`，执行 `pytest -k current_capability_hashes_recompute` 得 `1 failed`，原因 `AttributeError: inspect_current_capability_requests`，exit1。

## 最小实现与新鲜验证

| 项 | 命令／结果 |
| --- | --- |
| 源码 | `aip_solution_pack_publisher.py` 将原 Capability payload/hash 构造提成一个纯 `_capability_requests`，原 `_publish` 调同一函数；新增只读 `inspect_current_capability_requests`。没有新数据库写、迁移、鉴权绕过、Host 启动。 |
| 专项／相邻 | `pytest test_aip6_ecommerce_solution_pack.py`：`12 passed, 1 skipped`，exit0；该文件加签名预检、当前定义发布和分类门四文件：`29 passed, 1 skipped`，exit0。 |
| 当前签名包／权威库 | 只读调用新计算函数，当前签名树 `solution.ecommerce.growth/1.11.0` 十项 id/hash；容器内 `psql -U aos_app -d aos_current_preview_20260927 -Atc 'BEGIN READ ONLY; SELECT capability_id,content_hash FROM aip_capability_revision WHERE source_ref->>\'revision\'=\'1.11.0\' ORDER BY capability_id; COMMIT;'`，两者集合十项逐项一致，exit0。`material.collect` 双方均 `e50506079d86ed329e0052677d2f9bdbd46541f6f11b1465203710c0f24b58e2`；未读商城源。 |
| 静态／差异 | `py_compile` 两文件、`git diff --check`，均 exit0。其他 browser plugin/pnpm 工作树变动未触碰。 |

## 复审与剩余门

- 计算函数本身不验证签名，只有先由正式 `ManifestLoader`/Registry/当前 Installation 检查精确字节、签名指纹、撤销和 current generation，再以此 hash 比对 Catalog，才能作为就绪证据。当前 Installation approved3/active NULL；此 hash 一致**不**授权运行。
- 还需受限 Reader 权限、Installation active/current 签名来源、激活与每次调用最终事务重验；b34 strict xfail 保留，当前 Host/worker/Provider 继续关闭。当前真实库只读、Migration135；Growth1.13 正式发行、OIDC/issuer、八配置/六 Binding/Owner、自然首链均未因本波完成。
- 每日提醒若在本独立 08:40 重启后到达仍执行新一次最新 m1/权威卷 PG→API→Web 完整重启。纯函数是 b35 检查点，下一安全步骤是签名 Reader 负例与最终事务设计，不用假账户、local-only 签名树放行。
