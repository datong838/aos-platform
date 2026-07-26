import type { ReactNode } from "react";

export type BpArchLayer = {
  label: string;
  icon?: ReactNode;
  items?: string[];
};

export function BpArchitectureBar({ layers }: { layers: BpArchLayer[] }) {
  return (
    <div className="bp-arch-bar">
      {layers.map((layer, i) => (
        <div className="bp-arch-layer" key={`${layer.label}-${i}`}>
          <div className="bp-arch-layer-label">
            {layer.icon ? <span style={{ marginRight: 6 }}>{layer.icon}</span> : null}
            {layer.label}
          </div>
          <div className="bp-arch-layer-items">
            {(layer.items ?? []).map((item, j) => (
              <span className="bp-arch-item" key={`${item}-${j}`}>
                {item}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
