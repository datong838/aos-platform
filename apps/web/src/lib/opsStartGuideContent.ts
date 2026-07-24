/** 167 — 启停说明摘要（工程真源仍为 docs 72；本文件供系统端面展示） */
export type OpsGuideTierId =
  | "local"
  | "enterprise"
  | "group"
  | "saas"
  | "airgap";

export type OpsGuideTier = {
  id: OpsGuideTierId;
  title: string;
  align20a: string;
  who: string;
  topology: string;
  apply: string;
  start: string[];
  stop: string[];
  health: string[];
  ports?: { name: string; addr: string }[];
  honest?: string;
};

export const OPS_GUIDE_TIERS: OpsGuideTier[] = [
  {
    id: "local",
    title: "① 单机版",
    align20a: "Local-First 工作站",
    who: "试用 / PoC / 单机主权 · 日常开发默认",
    topology: "端与云同机；契约仍分离（端不直连引擎）",
    apply: "售前 PoC、研发、本机主权试用。常 1 Org，工作区可简化。",
    start: [
      "Windows：powershell -File scripts\\demo\\start-local.ps1",
      "macOS/Linux：bash scripts/demo/start-local.sh",
      "Docker Hub 不可达：栈已绿可忽略；缺镜像时 mac/Linux → start-local-native.sh，Win → start-local.ps1/加速（72 §1.3.1）",
      "桌面：先保证 API :8080 绿，再 cd apps/desktop && npm run tauri dev",
      "本机探活：探活 aos-api / PG·MinIO，并主动探活 Docker Hub",
    ],
    stop: [
      "bash scripts/demo/stop-local.sh",
      "含基础设施：bash scripts/demo/stop-local.sh --also-infra",
      "Windows：powershell -File scripts\\demo\\stop-local.ps1 [-AlsoInfra]",
    ],
    health: [
      "bash scripts/demo/health-check.sh --require-web",
      "Web http://127.0.0.1:5173 · API /v1/health · 本机探活",
      "成功标志：DEMO HEALTH OK",
    ],
    ports: [
      { name: "PostgreSQL", addr: ":5433" },
      { name: "MinIO", addr: ":9000" },
      { name: "aos-api", addr: "http://127.0.0.1:8080" },
      { name: "Web", addr: "http://127.0.0.1:5173" },
    ],
    honest: "不宣称生产 HA、不宣称客户机房已交付。",
  },
  {
    id: "enterprise",
    title: "② 标准企业版",
    align20a: "单机房私有化",
    who: "标准企业 · 数据主权 · 1 Org · 多工作区 · 单 Spoke",
    topology: "云在客户 DC/VPC；端（桌面+Web）指向客户入口域名",
    apply: "客户 IT 运维机房；我方可实施/维保。本机笔记本一般不起 start-local 冒充机房。",
    start: [
      "云：按交付包 / Apollo / Compose / Helm 在客户机房拉起（现场 Runbook 为准）",
      "探活：curl -fsS https://<客户-aos-api>/v1/health",
      "端：配置平台 API Base = 客户域名；桌面 channel.private.json 或 MDM 下发",
      "打包参考：bash scripts/ci/pack-desktop-mac.sh --check",
    ],
    stop: [
      "用户端：退出桌面 / 关浏览器 — 不停机房云",
      "客户运维：按机房 Runbook stop/scale — 不是 stop-local.sh",
    ],
    health: [
      "GET /v1/health 与依赖组件（客户运维/监控）",
      "桌面「平台地址」可达 · 登录客户 IdP",
      "工作区切换不串数（20a）抽检",
    ],
    honest: "生产 IdP / 真 HA 以合同为准；Bearer dev 禁止当客户签收。",
  },
  {
    id: "group",
    title: "③ 集团版",
    align20a: "Hub + 多 Spoke",
    who: "集团多地 / 多 Org / 数据面分 Spoke",
    topology: "Hub 控制面 + 多 Spoke 数据面；端连 Hub；禁止跨 Spoke 串读",
    apply: "Org 与 Spoke 绑定；工作区模型同 20a，部署边界在 Hub/Spoke。",
    start: [
      "研发明日：可先起单机栈，再开 Full Spoke mock（AOS_FULL_SPOKE_MODE=mock）",
      "生产目标：起 Hub → 各地 Spoke Agent 注册/心跳 → 端只配 Hub 入口",
      "不要把 Spoke 数据面 URL 散落给业务员",
    ],
    stop: ["分 Hub / Spoke 运维面分别停；端侧同标准企业"],
    health: [
      "Hub /v1/health",
      "Spoke 心跳或 mock catalog",
      "Org 切换后数据隔离；版本矩阵 /v1/ops/version-matrix",
    ],
    honest: "真多集群舰队仍后置；当前 Full Spoke 多为 helm-mock MVP，≠ 真舰队签收。",
  },
  {
    id: "saas",
    title: "④ SaaS 版",
    align20a: "托管 SKU · 多租户",
    who: "小公司包月/包年；每客户一 Org",
    topology: "云在我方多租户机房；端同构，只换 API Base / 证书 / 开通台",
    apply: "客户不装本机 Docker 平台；租户管理员只用端内组织/工作区。",
    start: [
      "云：我方机房常驻（客户无启停责任）",
      "端：安装 SaaS 渠道包或打开 Web 门户；Base 预置/只读",
      "我方运营：开通台创建租户 Org 与配额",
    ],
    stop: [
      "客户：仅退出端",
      "我方：多租户运维 / 开通台暂停 — 不是客户本机 stop-local",
    ],
    health: [
      "curl -fsS https://<saas-api>/v1/health",
      "开通台租户状态 · 配额 · Org 隔离抽检",
    ],
  },
  {
    id: "airgap",
    title: "气隙 / Ferry 变体",
    align20a: "②/③ 高安全加严（非独立销售主档）",
    who: "无外网或单向摆渡现场",
    topology: "内网 API Base；升级靠签名 Bundle + Ferry 摆渡",
    apply: "销售上仍报标准企业/集团 + 气隙选项。",
    start: [
      "端仅配内网平台地址；渠道包可锁死域名",
      "升级：签名包经 Ferry 摆渡进现场（见 Ferry 现场规程）",
    ],
    stop: ["同挂靠的标准企业或集团分档；摆渡通道按现场关闭"],
    health: ["内网 /v1/health · Ferry 探活 · 签名校验（现场加严）"],
    honest: "现场大镜像走 onsite pack；默认演示路径不依赖多 GB CI。",
  },
];
