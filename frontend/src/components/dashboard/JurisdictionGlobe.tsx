"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import type { GlobePoint } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

const Globe = dynamic(() => import("react-globe.gl").then((m) => m.default), {
  ssr: false,
  loading: () => (
    <div className="flex h-[400px] w-full items-center justify-center rounded-xl border border-border bg-muted/20">
      <p className="text-sm text-muted-foreground">Loading globe…</p>
    </div>
  ),
});

type JurisdictionGlobeProps = {
  points: GlobePoint[];
  activeJurisdiction: string | null;
  onSelectJurisdiction: (code: string | null) => void;
};

export function JurisdictionGlobe({
  points,
  activeJurisdiction,
  onSelectJurisdiction,
}: JurisdictionGlobeProps) {
  const [hovered, setHovered] = React.useState<string | null>(null);
  const [size, setSize] = React.useState({ w: 800, h: 400 });

  React.useEffect(() => {
    const onResize = () =>
      setSize({ w: window.innerWidth, h: 400 });
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const pointAltitude = (p: GlobePoint) => (p.type === "regulator" ? 0.4 : 0.2);
  const pointRadius = (p: GlobePoint) => (p.type === "regulator" ? 0.8 : 0.5);
  const pointColor = (p: GlobePoint) =>
    p.jurisdiction === activeJurisdiction ? "#00ff88" : "#00ff8866";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Jurisdiction Radar</h3>
        <div className="flex gap-3">
          <Badge variant="secondary" className="gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" /> Regulator
          </Badge>
          <Badge variant="secondary" className="gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-primary/60" /> Vendor
          </Badge>
          {activeJurisdiction && (
            <Badge
              variant="outline"
              className="cursor-pointer"
              onClick={() => onSelectJurisdiction(null)}
            >
              Clear filter
            </Badge>
          )}
        </div>
      </div>
      <div className="relative overflow-hidden rounded-xl border border-border bg-black/40">
        <div className="absolute inset-0 z-0 rounded-xl bg-[radial-gradient(ellipse_at_center,rgba(0,255,136,0.06)_0%,transparent_70%)]" />
        <div className="relative z-10 h-[400px] w-full">
          <Globe
            width={size.w}
            height={size.h}
            backgroundColor="rgba(5,6,7,0)"
            globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
            pointsData={points}
            pointLat={(d) => (d as GlobePoint).lat}
            pointLng={(d) => (d as GlobePoint).lng}
            pointAltitude={(d) => pointAltitude(d as GlobePoint)}
            pointRadius={(d) => pointRadius(d as GlobePoint)}
            pointColor={(d) => pointColor(d as GlobePoint)}
            pointLabel={(d) =>
              `${(d as GlobePoint).label} (${(d as GlobePoint).jurisdiction}) — ${(d as GlobePoint).type}`
            }
            onPointClick={(p) => {
              const pt = p as GlobePoint;
              onSelectJurisdiction(
                activeJurisdiction === pt.jurisdiction ? null : pt.jurisdiction
              );
            }}
            onPointHover={(p) => setHovered((p as GlobePoint | null)?.label ?? null)}
          />
        </div>
        {hovered && (
          <div className="absolute bottom-4 left-4 rounded-lg border border-border bg-card/90 px-3 py-2 text-xs backdrop-blur-sm">
            {hovered}
          </div>
        )}
      </div>
    </div>
  );
}
