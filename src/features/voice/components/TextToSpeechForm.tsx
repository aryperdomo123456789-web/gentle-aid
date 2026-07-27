import { useState, type ReactNode } from "react";

import { Field, SelectInput, SubmitButton, TextArea } from "@/components/form";
import { MutationSelect } from "@/components/MutationSelect";
import { AudioFormatField } from "./AudioFormatField";
import { ScriptDoctorChat } from "./ScriptDoctorChat";

type Props = {
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  maxChars: number;
  busy: boolean;
  disabled: boolean;
  picker: ReactNode;
};

/** Aba "Texto → narração": roteiro longo vira narração contínua. */
export function TextToSpeechForm({ onSubmit, maxChars, busy, disabled, picker }: Props) {
  // O roteiro é controlado para o Doutor de Roteiro poder reescrevê-lo.
  const [text, setText] = useState("");
  const [speed, setSpeed] = useState("1");
  const [style, setStyle] = useState("0.15");

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Field
        label="Roteiro"
        hint={`Até ${maxChars.toLocaleString("pt-BR")} caracteres — textos longos viram uma narração contínua.`}
      >
        {(id) => (
          <TextArea
            id={id}
            name="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Cole aqui o roteiro que será narrado…"
            maxLength={maxChars}
          />
        )}
      </Field>

      <ScriptDoctorChat
        value={text}
        onChange={setText}
        maxChars={maxChars}
        onStyleHint={(hint) => {
          setSpeed(hint.speed);
          setStyle(String(hint.style));
        }}
      />

      {picker}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
        <Field label="Velocidade">
          {(id) => (
            <SelectInput id={id} name="speed" value={speed} onChange={(e) => setSpeed(e.target.value)}>
              <option value="0.9">Pausada (0.9x)</option>
              <option value="1">Natural (1.0x)</option>
              <option value="1.1">Ágil (1.1x)</option>
            </SelectInput>
          )}
        </Field>
        <AudioFormatField label="Formato" />
      </div>

      <Field label="Expressividade" hint="O estilo escolhido no Doutor de Roteiro já ajusta este campo.">
        {(id) => (
          <SelectInput id={id} name="style" value={style} onChange={(e) => setStyle(e.target.value)}>
            <option value="0">Neutra — leitura limpa</option>
            <option value="0.15">Narrador — padrão do mercado</option>
            <option value="0.3">Envolvente — true crime / documentário</option>
            <option value="0.45">Dramática — storytelling viral</option>
          </SelectInput>
        )}
      </Field>

      <MutationSelect
        defaultValue="auto"
        label="Esterilização"
        hint="Áudio final sem rastro de origem."
      />

      <SubmitButton busy={busy} disabled={disabled || text.trim().length < 2}>
        {busy ? "Narrando…" : "Gerar narração"}
      </SubmitButton>
    </form>
  );
}
