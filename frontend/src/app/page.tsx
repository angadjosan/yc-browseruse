"use client";

import dynamic from "next/dynamic";

const LandingContent = dynamic(
  () =>
    Promise.all([
      import("@/components/landing/GradientBackground"),
      import("@/components/landing/HeroCard"),
    ]).then(([{ GradientBackground }, { HeroCard }]) => {
      function LandingView() {
        return (
          <div className="relative min-h-screen">
            <GradientBackground />
            <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 py-16">
              <HeroCard />
            </div>
          </div>
        );
      }
      LandingView.displayName = "LandingView";
      return LandingView;
    }),
  { ssr: false }
);

export default function LandingPage() {
  return <LandingContent />;
}
