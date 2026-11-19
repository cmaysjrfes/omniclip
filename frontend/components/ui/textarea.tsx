import * as React from "react";
import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea data-slot="textarea" className={cn(
      "placeholder:text-muted-foreground border-input flex field-sizing-content min-h-16 w-full rounded-md border bg-input/30 px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:opacity-50",
      className)} {...props} />
  );
}
export { Textarea };
