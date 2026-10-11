# 栖月汇八工作台保留与目录分类实测

原有限LOGIN及READ ONLY目录来源两次独立读取一致：org-org/dev-project的legacy目录为空，runtime候选有三个有效安装叶、各四包，共12行；dev-org/dev-project两目录均空。异常不得计为零项；本次无异常。

两个最新历史安装407059df/89975129持有真实published Core1.4.2、Platform1.23.2、Growth1.10.2、Operations1.2.2。原ManifestLoader使用保留签名根读取Growth1.10.2与Operations1.2.2，得到七加一共8模块，哈希与本轮目录读回一致。没有改写为Core1.4.3/Growth1.13.0；它们仍属另一个最新版本发布任务。

八路由：cockpit、content-campaign、operations、creator-growth、media-studio、analyst、price-governance、customer，均在/workshop下。模块源文件与签名存在不等于页面运行通过。

前端apps/web/src/pages/s2/ecommerce/routes.tsx实际同时读取两目录：有效runtime项进入RuntimeWorkshopHost；无runtime且无legacy项落入用户截图的EcommerceWorkshopHost空态。因此当前没有证据表明缺少新版前端接线。原运行目录仍要求ready、enabled、operationFence=false、当前UI资源会话，不能删除legacy排除条件绕过运行边界。恢复库0enabled与已知全fenced状态仍需正式配置链解决；当前主API尚未接回恢复库。登录模式与独立发布身份问题分别核对，不宣称已经接入。

本轮验证：真实有限LOGIN预检、四个scope/source组合各两独立读取、两签名包八模块解析、前端路由只读复审。未修改产品代码或数据库，未启动Host/worker/Provider、未重放未知效果。Goal与全恢复Task保持active。

已登记候选：A 主线恢复登录/历史安装配置与真实API→Web八页（已授权恢复；依赖既有登录来源、当前Owner/配置/资源门）；B 最新Core1.4.3/Growth1.13.0发布及安装（已有恢复授权；依赖独立真实发布身份）。本轮执行A的安装与目录实测，不把B作为所有历史管理展示的必要条件。后续先按真实runtime_view逐项只读定位当前安装阻断，再在原控制面授权范围内修复。
