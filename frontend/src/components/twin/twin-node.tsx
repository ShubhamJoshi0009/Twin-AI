"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { Activity, Banknote, Boxes, Factory, ShoppingCart, Truck, UserRound, Users } from "lucide-react";
import { cn } from "@/lib/utils";

const NODE_ICONS: Record<string, typeof Activity> = {
  business: Activity,
  products: Boxes,
  warehouses: Factory,
  suppliers: Truck,
  customers: Users,
  employees: UserRound,
  sales: ShoppingCart,
  finance: Banknote,
};

export interface TwinNodeData {
  label: string;
  type: string;
  value?: string;
  health?: number;
  detail?: string;
  [key: string]: unknown;
}

export type TwinNodeType = Node<TwinNodeData, "twin">;

function healthColor(health: number) {
  if (health >= 75) return "border-success/50 bg-success/10";
  if (health >= 50) return "border-warning/50 bg-warning/10";
  return "border-destructive/50 bg-destructive/10";
}

/** Custom enterprise node rendered inside the React Flow canvas. */
const TwinNode = memo(({ data, selected }: NodeProps<TwinNodeType>) => {
  const Icon = NODE_ICONS[data.type] ?? Activity;
  const isBusiness = data.type === "business";

  return (
    <div
      className={cn(
        "group relative flex w-44 flex-col items-center gap-2 rounded-xl border bg-card px-4 py-3 shadow-md transition-all duration-300",
        isBusiness
          ? "border-primary/60 bg-primary/5 shadow-primary/10"
          : healthColor(data.health ?? 70),
        selected && "ring-2 ring-primary"
      )}
    >
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-primary/60" />
      <div
        className={cn(
          "flex h-10 w-10 items-center justify-center rounded-full transition-transform duration-300 group-hover:scale-110",
          isBusiness ? "bg-primary text-primary-foreground shadow-lg shadow-primary/30" : "bg-card shadow"
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="text-center">
        <p className={cn("text-sm font-semibold leading-tight", isBusiness && "text-primary")}>{data.label}</p>
        {data.value && <p className="text-xs tabular-nums text-muted-foreground">{data.value}</p>}
      </div>
      {!isBusiness && data.health !== undefined && (
        <div className="flex items-center gap-1.5">
          <span className={cn("h-1.5 w-1.5 rounded-full", data.health >= 75 ? "bg-success" : data.health >= 50 ? "bg-warning" : "bg-destructive")} />
          <span className="text-[10px] text-muted-foreground">{data.health}/100</span>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0 !bg-primary/60" />
    </div>
  );
});

TwinNode.displayName = "TwinNode";

export default TwinNode;
