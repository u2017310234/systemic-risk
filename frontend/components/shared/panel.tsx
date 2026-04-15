import { cn } from "@/lib/utils";

export function Panel({
  children,
  className
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-[28px] border border-line/80 bg-panel/90 p-5 shadow-glow backdrop-blur",
        className
      )}
    >
      {children}
    </section>
  );
}
