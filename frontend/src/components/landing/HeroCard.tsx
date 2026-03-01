"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { DemoRunLoop } from "./DemoRunLoop";
import { motion } from "framer-motion";
import { FileCheck, RefreshCw, LayoutList, MessageSquare } from "lucide-react";

export function HeroCard() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="relative z-10 mx-auto max-w-2xl rounded-2xl border border-border bg-black/40 p-8 shadow-2xl backdrop-blur-xl border-glow"
    >
      <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
        Compliance Change Radar
      </h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Describe your product, and we automatically watch every regulation and vendor policy that affects you — and ticket your team the second something changes.
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        We search across multi-step flows, capture screenshots + hashes, diff changes, summarize impact, then create a Linear/Jira ticket with an audit-ready evidence bundle.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button asChild size="lg" className="glow-green">
          <Link href="/app">Create your radar</Link>
        </Button>
        <Button asChild variant="outline" size="lg">
          <a href="#demo">View demo change</a>
        </Button>
      </div>
      <DemoRunLoop />
      <div id="demo" className="mt-8 flex flex-wrap items-center justify-center gap-6 border-t border-border pt-6">
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <FileCheck className="h-4 w-4 text-primary" /> Evidence bundle
        </span>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <RefreshCw className="h-4 w-4 text-primary" /> Self-healing
        </span>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <LayoutList className="h-4 w-4 text-primary" /> Linear/Jira
        </span>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <MessageSquare className="h-4 w-4 text-primary" /> Slack
        </span>
      </div>
    </motion.div>
  );
}
