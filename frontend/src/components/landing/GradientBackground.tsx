"use client";

/**
 * CSS-only animated gradient background (green/black).
 * Replaces ShaderGradient to avoid @react-three/fiber runtime errors.
 */
export function GradientBackground() {
  return (
    <div
      className="fixed inset-0 z-0 overflow-hidden bg-[#050607]"
      aria-hidden
    >
      {/* Animated gradient orbs */}
      <div
        className="absolute -left-1/4 -top-1/4 h-[80vh] w-[80vw] rounded-full opacity-40 blur-3xl"
        style={{
          background:
            "radial-gradient(circle, rgba(0,255,136,0.35) 0%, rgba(0,59,31,0.2) 40%, transparent 70%)",
          animation: "gradient-pulse 8s ease-in-out infinite",
        }}
      />
      <div
        className="absolute -bottom-1/4 -right-1/4 h-[70vh] w-[70vw] rounded-full opacity-30 blur-3xl"
        style={{
          background:
            "radial-gradient(circle, rgba(0,229,255,0.15) 0%, rgba(0,59,31,0.15) 50%, transparent 70%)",
          animation: "gradient-pulse 10s ease-in-out infinite reverse",
        }}
      />
      <div
        className="absolute left-1/2 top-1/2 h-[60vmin] w-[60vmin] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-20 blur-3xl"
        style={{
          background:
            "radial-gradient(circle, rgba(0,255,136,0.25) 0%, transparent 60%)",
          animation: "gradient-pulse 12s ease-in-out infinite",
          animationDelay: "1s",
        }}
      />
      {/* Subtle grid / noise overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />
    </div>
  );
}
