"use client";

import { ShaderGradientCanvas, ShaderGradient } from "@shadergradient/react";

export function ShaderBackground() {
  return (
    <div className="fixed inset-0 z-0 overflow-hidden">
      <ShaderGradientCanvas
        style={{ position: "absolute", inset: 0 }}
        pixelDensity={1}
        fov={45}
        pointerEvents="none"
      >
        <ShaderGradient
          animate="on"
          type="plane"
          color1="#00ff88"
          color2="#003b1f"
          color3="#0b1220"
          uSpeed={0.4}
          uStrength={4}
          uDensity={1.3}
          uFrequency={5.5}
          uAmplitude={1}
          uTime={0}
          cAzimuthAngle={180}
          cPolarAngle={90}
          cDistance={3.6}
          cameraZoom={1}
          positionX={-1.4}
          positionY={0}
          positionZ={0}
          rotationX={0}
          rotationY={10}
          rotationZ={50}
          reflection={0.1}
          wireframe={false}
          shader="defaults"
          lightType="3d"
          envPreset="city"
          grain="on"
        />
      </ShaderGradientCanvas>
    </div>
  );
}
