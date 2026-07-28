import { CAPTION_PANELS, type PanelId } from "@/features/captions/panels";
import { cn } from "@/lib/utils";

type Props = {
  active: PanelId | null;
  onSelect: (panel: PanelId | null) => void;
};

/** Rail vertical de ferramentas (horizontal e rolável no mobile). */
export function StudioRail({ active, onSelect }: Props) {
  return (
    <nav
      aria-label="Ferramentas"
      className="scroll-x flex shrink-0 gap-1 overflow-x-auto border-b border-border bg-card px-1 py-1 md:w-16 md:flex-col md:items-center md:overflow-x-visible md:overflow-y-auto md:border-b-0 md:border-r md:px-0 md:py-2 lg:w-[74px]"
    >
      {CAPTION_PANELS.map(({ id, label, icon: Icon }) => {
        const isActive = active === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onSelect(isActive ? null : id)}
            aria-pressed={isActive}
            className={cn(
              "flex min-h-14 w-16 shrink-0 flex-col items-center justify-center gap-1 rounded-lg px-1 py-2 text-[10px] leading-tight transition md:w-full",
              isActive
                ? "bg-primary/15 text-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className={cn("size-5", isActive && "text-primary")} />
            {label}
          </button>
        );
      })}
    </nav>
  );
}
