"use client";

import * as React from "react";
import { motion } from "framer-motion";

const STEPS = [
  "Searching",
  "Navigating",
  "Capturing",
  "Hashing",
  "Diff detected",
  "Ticket created",
];

export function DemoRunLoop() {
  return (
    <div className="mt-6 rounded-lg border border-border bg-black/30 p-4 backdrop-blur-sm">
      <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        Live demo run
      </p>
      <StepCycler steps={STEPS} />
    </div>
  );
}

function StepCycler({ steps }: { steps: string[] }) {
  const [index, setIndex] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(() => {
      setIndex((i) => (i + 1) % steps.length);
    }, 1000);
    return () => clearInterval(t);
  }, [steps.length]);

  const progress = ((index + 1) / steps.length) * 100;

  return (
    <div className="space-y-3">
      <motion.div
        key={steps[index]}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.2 }}
        className="text-sm font-medium text-primary"
      >
        {steps[index]}
      </motion.div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.3 }}
        />
      </div>
    </div>
  );
}

