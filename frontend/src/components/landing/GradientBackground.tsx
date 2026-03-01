"use client";

/**
 * CSS-only animated gradient background (green/black).
 * Replaces ShaderGradient to avoid @react-three/fiber runtime errors.
 */
export function GradientBackground() {
  return (
    <div
      className="fixed inset-0 z-0 overflow-hidden bg-[#060807]"
      aria-hidden
    >
      {/* Animated gradient orbs - green nighty night */}
      <div
        className="absolute -left-1/4 -top-1/4 h-[80vh] w-[80vw] rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle, rgba(0,255,136,0.4) 0%, rgba(0,80,45,0.25) 40%, transparent 70%)",
          animation: "gradient-pulse 8s ease-in-out infinite",
        }}
      />
      <div
        className="absolute -bottom-1/4 -right-1/4 h-[70vh] w-[70vw] rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle, rgba(0,255,136,0.12) 0%, rgba(0,59,31,0.2) 50%, transparent 70%)",
          animation: "gradient-pulse 10s ease-in-out infinite reverse",
        }}
      />
      <div
        className="absolute left-1/2 top-1/2 h-[60vmin] w-[60vmin] -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle, rgba(0,255,136,0.28) 0%, transparent 60%)",
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
