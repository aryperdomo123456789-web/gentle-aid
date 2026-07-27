import { Field, SelectInput } from "@/components/form";

/** Níveis de esterilização compartilhados por todas as ferramentas. */
export const MUTATION_LEVELS = [
  { value: "auto", label: "Auto inteligente — escolhe o melhor perfil" },
  { value: "off", label: "Desativado — só limpeza de metadados" },
  { value: "leve", label: "Leve — mutação mínima, qualidade máxima" },
  { value: "media", label: "Média — recomendado (crop, EQ, PTS, áudio)" },
  { value: "agressiva", label: "Agressiva — + ruído temporal e filtros de banda" },
  { value: "extrema", label: "Extrema — máximo bypass de fingerprint" },
] as const;

export function MutationSelect({
  name = "mutation",
  defaultValue = "auto",
  value,
  onChange,
  label = "Nível de esterilização",
  hint = "Todo arquivo sai virgem: metadados destruídos, identidade forjada e hash inédito. O nível controla só a intensidade da mutação estrutural.",
}: {
  name?: string;
  defaultValue?: string;
  /** Modo controlado — quando informado, `defaultValue` é ignorado. */
  value?: string;
  onChange?: (value: string) => void;
  label?: string;
  hint?: string;
}) {
  const controlled = value !== undefined;
  return (
    <Field label={label} hint={hint}>
      {(id) => (
        <SelectInput
          id={id}
          name={name}
          {...(controlled
            ? { value, onChange: (e: React.ChangeEvent<HTMLSelectElement>) => onChange?.(e.target.value) }
            : { defaultValue })}
        >
          {MUTATION_LEVELS.map((level) => (
            <option key={level.value} value={level.value}>
              {level.label}
            </option>
          ))}
        </SelectInput>
      )}
    </Field>
  );
}

