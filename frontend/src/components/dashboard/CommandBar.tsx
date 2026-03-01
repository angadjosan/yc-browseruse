"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";

export function CommandBar() {
  const [query, setQuery] = useState("");

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Describe what to watch… (e.g., 'GDPR guidance for AI profiling', 'Stripe ToS', 'HIPAA tracking pixels')"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9 bg-background/50"
        />
      </div>
      <Button className="shrink-0">Create watch</Button>
    </div>
  );
}
