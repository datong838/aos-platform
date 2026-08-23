import type { ReactNode } from "react";

/**
 * 三层架构定位条中的层标识。
 * - L1: 模型供应商
 * - L2: 模型路由
 * - L3: 当前模型（模型目录）
 * - AIP: AIP 应用（智能体调用）
 */
export type BpArchLayerId = "L1" | "L2" | "L3" | "AIP";

export type BpArchLayer = {
  /**层的稳定 ID，用于 activeLayer 比较与 onLayerClick 回调*/
  id: BpArchLayerId;
  /**层标签，如 "模型供应商"*/
  label: string;
  /**层的简短描述，如 "凭证管理"*/
  hint?: string;
  /**层入口链接或动作文本，如 "进入 →"*/
  link?: string;
  /**自定义图标（可选）*/
  icon?: ReactNode;
};

/**层样式信息（导出便于测试断言）*/
export type LayerStyleInfo = {
  id: BpArchLayerId;
  isActive: boolean;
  className: string;
};

/**默认四层架构数据（L1→L2→L3→AIP），便于直接使用*/
export const DEFAULT_ARCH_LAYERS: BpArchLayer[] = [
  { id: "L1", label: "模型供应商", hint: "凭证管理", link: "进入 →" },
  { id: "L2", label: "模型路由", hint: "流量策略 · 熔断", link: "进入 →" },
  { id: "L3", label: "模型目录", hint: "可发现 → 注册" },
  { id: "AIP", label: "智能体调用", hint: "选模型 → 推理" },
];

/**计算单个层的样式信息（纯函数，便于测试）*/
export function getLayerStyle(
  layerId: BpArchLayerId,
  activeLayer?: BpArchLayerId | null,
): LayerStyleInfo {
  const isActive = activeLayer != null && activeLayer === layerId;
  const classes = ["bp-arch-layer"];
  if (isActive) classes.push("is-active");
  if (layerId === "AIP") classes.push("is-aip");
  return {
    id: layerId,
    isActive,
    className: classes.join(" "),
  };
}

/**层标签文案：当前层追加「· 当前」（对齐视觉稿）*/
export function layerTagText(
  layerId: BpArchLayerId,
  activeLayer?: BpArchLayerId | null,
): string {
  const labels: Record<BpArchLayerId, string> = {
    L1: "供应商配置",
    L2: "路由策略",
    L3: "模型目录",
    AIP: "智能体应用",
  };
  if (activeLayer != null && activeLayer === layerId) {
    return `${labels[layerId]} · 当前`;
  }
  return labels[layerId];
}

/**箭头连接符（纯展示）*/
function ArchArrow() {
  return (
    <svg
      className="bp-arch-arrow"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      aria-hidden="true"
    >
      <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * 三层架构定位条（AIP Model Catalog 视觉规范）。
 *
 * L1（模型供应商）→ L2（模型路由）→ L3（当前模型）→ AIP 应用
 *
 * - 每层可点击，蓝色高亮当前层（activeLayer），灰色非活跃层
 * - 层与层之间有箭头连接
 * - 支持 onLayerClick 回调
 */
export function BpArchitectureBar({
  layers = DEFAULT_ARCH_LAYERS,
  activeLayer,
  onLayerClick,
  title,
}: {
  /**四层架构数据，默认使用 DEFAULT_ARCH_LAYERS*/
  layers?: BpArchLayer[];
  /**当前高亮的层 ID；为空则无高亮*/
  activeLayer?: BpArchLayerId | null;
  /**层点击回调*/
  onLayerClick?: (layerId: BpArchLayerId, layer: BpArchLayer) => void;
  /**可选的定位条标题（渲染在条上方）*/
  title?: ReactNode;
}) {
  return (
    <div className="bp-arch-bar" role="navigation" aria-label="三层架构定位">
      {title ? <div className="bp-arch-bar-title">{title}</div> : null}
      <div className="bp-arch-bar-track">
        {layers.map((layer, i) => {
          const styleInfo = getLayerStyle(layer.id, activeLayer);
          const clickable = !!onLayerClick;
          return (
            <div className="bp-arch-segment" key={layer.id}>
              <div
                className={styleInfo.className}
                role={clickable ? "button" : undefined}
                tabIndex={clickable ? 0 : undefined}
                aria-current={styleInfo.isActive ? "step" : undefined}
                aria-pressed={styleInfo.isActive ? true : undefined}
                onClick={
                  clickable
                    ? () => onLayerClick!(layer.id, layer)
                    : undefined
                }
                onKeyDown={
                  clickable
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onLayerClick!(layer.id, layer);
                        }
                      }
                    : undefined
                }
                style={
                  clickable
                    ? { cursor: "pointer" }
                    : undefined
                }
              >
                <div className="bp-arch-layer-tag">
                  {layerTagText(layer.id, activeLayer)}
                </div>
                <div className="bp-arch-layer-label">
                  {layer.icon ? (
                    <span className="bp-arch-layer-icon">{layer.icon}</span>
                  ) : null}
                  {layer.label}
                </div>
                {layer.hint ? (
                  <div className="bp-arch-layer-hint">{layer.hint}</div>
                ) : null}
                {layer.link ? (
                  <span className="bp-arch-layer-link">{layer.link}</span>
                ) : null}
              </div>
              {i < layers.length - 1 ? <ArchArrow /> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
