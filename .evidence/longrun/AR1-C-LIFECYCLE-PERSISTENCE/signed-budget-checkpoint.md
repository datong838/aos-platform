# AR1-c 原预算引用联合检查点

2026-09-06；基线m1@f0f28076/AOS-000543。主波继续。

原签名配置联合预算替身已替换为aip10_001真实表定义＋原BudgetRevision materialize＋read_current_budget_ref。专用18432/ar1c_临时schema内明确测试预算，无真实预算变更或Provider。ConfigurationAuthorization精确budget/aip.budget_revision插槽使用原连接/租户/ExactRef，每次读取不缓存，不复制内核预算算法。

新增原预算表及authority断言首先Red（UndefinedTable，12.76s），接线后真实签名Registry/Installation/OCI/准备/验证/配置/启用/停用联合1passed18.44s。配置fence已提交后测试head指向不存在的revision2，原reader明确拒绝当前引用且完整state不变；隔离故障注入恢复head1后续跑，后续ACK回滚重投保持状态。此例是引用失效，不冒充完整预算升级/撤销流程。预算Receipt计数0，不证明hold已实现。

累计894passed、6既有warnings、127.69s、exit0；原预算失效/hash/角色/RLS/头锁专项保留在累计内。git diff --check通过。Prime独立复审无新增实质缺陷；无页面改动，不称新浏览器验收。

角色/data/policy与drain仍命名测试来源，正式费用预留/业务broker未完成，新业务场景0，历史44/81未变。下一段组合签名查询接纳、当前安装/epoch/权限和受限只读查询为内部broker，继续正式引用与排空、完整卸载重装；不开放公共业务入口。
