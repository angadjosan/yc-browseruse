import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/20 text-primary",
        secondary: "border-border bg-muted text-muted-foreground",
        destructive: "border-transparent bg-destructive/20 text-destructive",
        outline: "text-foreground border-border",
        healthy: "border-transparent bg-primary/20 text-primary",
        degraded: "border-transparent bg-warning/20 text-warning",
        low: "border-transparent bg-primary/15 text-primary",
        med: "border-transparent bg-warning/20 text-amber-400",
        high: "border-transparent bg-destructive/20 text-destructive",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
