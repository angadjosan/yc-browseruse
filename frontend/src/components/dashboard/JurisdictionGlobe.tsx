"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import type { GlobePoint } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Globe as GlobeIcon, MapPin } from "lucide-react";

const Globe = dynamic(() => import("react-globe.gl").then((m) => m.default), {
  ssr: false,
  loading: () => (
    <div className="flex h-[420px] w-full items-center justify-center rounded-2xl border border-primary/20 bg-muted/30">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <div className="h-10 w-10 animate-pulse rounded-full bg-primary/20" />
        <p className="text-sm">Loading Jurisdiction Radar…</p>
      </div>
    </div>
  ),
});

type JurisdictionGlobeProps = {
  points: GlobePoint[];
  activeJurisdiction: string | null;
  onSelectJurisdiction: (code: string | null) => void;
};

const GLOBE_HEIGHT = 420;

export function JurisdictionGlobe({
  points,
  activeJurisdiction,
  onSelectJurisdiction,
}: JurisdictionGlobeProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [size, setSize] = React.useState({ w: 900, h: GLOBE_HEIGHT });
  const [hovered, setHovered] = React.useState<GlobePoint | null>(null);

  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => {
      const w = el.offsetWidth;
      setSize({ w, h: GLOBE_HEIGHT });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const pointAltitude = (p: GlobePoint) => (p.type === "regulator" ? 0.5 : 0.28);
  const pointRadius = (p: GlobePoint) => (p.type === "regulator" ? 1 : 0.65);
  const pointColor = (p: GlobePoint) =>
    p.jurisdiction === activeJurisdiction
      ? "#00ff88"
      : hovered?.label === p.label
        ? "#5cffaa"
        : "#00ff8888";

  return (
    <section className="mx-auto w-full max-w-5xl">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <GlobeIcon className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-foreground">
              Jurisdiction Radar
            </h2>
            <p className="text-xs text-muted-foreground">
              Click a point to filter by jurisdiction
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="gap-1.5 border-primary/20 bg-primary/5">
            <span className="h-2 w-2 rounded-full bg-primary shadow-[0_0_8px_var(--primary)]" />
            Regulator
          </Badge>
          <Badge variant="secondary" className="gap-1.5 border-primary/20 bg-primary/5">
            <span className="h-2 w-2 rounded-full bg-primary/70" />
            Vendor
          </Badge>
          {activeJurisdiction && (
            <Badge
              variant="outline"
              className="cursor-pointer border-primary/30 text-primary hover:bg-primary/10"
              onClick={() => onSelectJurisdiction(null)}
            >
              Clear filter
            </Badge>
          )}
        </div>
      </div>

      <div
        ref={containerRef}
        className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-b from-muted/40 to-black/60 shadow-[0_0_40px_-12px_rgba(0,255,136,0.15)]"
      >
        {/* Sweep ring overlay */}
        <div className="sweep-ring" aria-hidden />
        <div
          className="sweep-ring"
          style={{ animationDelay: "1s" }}
          aria-hidden
        />
        <div
          className="sweep-ring"
          style={{ animationDelay: "2s" }}
          aria-hidden
        />

        <div className="relative flex justify-center" style={{ height: GLOBE_HEIGHT }}>
          <Globe
            width={size.w}
            height={size.h}
            backgroundColor="rgba(6,8,7,0)"
            globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
            showAtmosphere
            atmosphereColor="#00ff8844"
            atmosphereAltitude={0.18}
            pointsData={points}
            pointLat={(d) => (d as GlobePoint).lat}
            pointLng={(d) => (d as GlobePoint).lng}
            pointAltitude={(d) => pointAltitude(d as GlobePoint)}
            pointRadius={(d) => pointRadius(d as GlobePoint)}
            pointColor={(d) => pointColor(d as GlobePoint)}
            pointLabel={(d) => {
              const p = d as GlobePoint;
              return `${p.label} · ${p.jurisdiction} · ${p.type}`;
            }}
            onPointClick={(p) => {
              const pt = p as GlobePoint;
              onSelectJurisdiction(
                activeJurisdiction === pt.jurisdiction ? null : pt.jurisdiction
              );
            }}
            onPointHover={(p) => setHovered((p as GlobePoint | null) ?? null)}
          />
        </div>

        {hovered && (
          <div className="absolute bottom-4 left-1/2 z-20 -translate-x-1/2 rounded-xl border border-primary/25 bg-card/95 px-4 py-3 shadow-lg backdrop-blur-md">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <MapPin className="h-4 w-4 text-primary" />
              {hovered.label}
            </div>
            <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
              <span>{hovered.jurisdiction}</span>
              <span>·</span>
              <span className="capitalize">{hovered.type}</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
