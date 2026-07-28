import { Clock3, Image as ImageIcon, Palette, Search, Shield, ShieldCheck, Sparkles, Type, Upload, Wand2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";

/** Painéis laterais do Estúdio de Legendas (rail estilo Canva). */
export type PanelId =
  | "uploads"
  | "pesquisa"
  | "estilos"
  | "texto"
  | "animacao"
  | "cores"
  | "esterilizar"
  | "exportar"
  | "jobs"
  | "historico";

export type PanelDefinition = { id: PanelId; label: string; icon: LucideIcon };

export const CAPTION_PANELS: PanelDefinition[] = [
  { id: "uploads", label: "Uploads", icon: Upload },
  { id: "pesquisa", label: "Pesquisar", icon: Search },
  { id: "estilos", label: "Estilos", icon: Sparkles },
  { id: "texto", label: "Texto", icon: Type },
  { id: "animacao", label: "Animação", icon: Wand2 },
  { id: "cores", label: "Cores", icon: Palette },
  { id: "esterilizar", label: "Esterilizar", icon: Shield },
  { id: "exportar", label: "Exportar", icon: ShieldCheck },
  { id: "jobs", label: "Job", icon: ImageIcon },
  { id: "historico", label: "Histórico", icon: Clock3 },
];

export function panelLabel(id: PanelId): string {
  return CAPTION_PANELS.find((panel) => panel.id === id)?.label ?? "";
}
