import type { ReactNode } from "react";

/* ==========================================================================
   Alert Banner — variante « mono ».
   Un avertissement de notice technique, pas un message d'erreur système :
   filet épais, pictogramme dessiné, aucune couleur de fond criarde.
   Seule exception au vert signal dans cette page, avec le meilleur choix
   et le bouton d'action.
   ========================================================================== */

function WarningMark() {
  return (
    <span
      aria-hidden="true"
      className="flex size-9 shrink-0 items-center justify-center bg-signal"
    >
      <svg viewBox="0 0 24 24" className="size-5" fill="none">
        <path
          d="M12 4.5 2.8 20h18.4L12 4.5Z"
          stroke="var(--color-ink)"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path
          d="M12 10v4.2"
          stroke="var(--color-ink)"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
        <circle cx="12" cy="17.2" r="1" fill="var(--color-ink)" />
      </svg>
    </span>
  );
}

export function AlertBanner({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <aside
      role="note"
      className="flex flex-col gap-4 border border-line border-l-[3px] border-l-alert bg-surface p-6 sm:flex-row sm:gap-6 sm:p-8"
    >
      <WarningMark />
      <div className="min-w-0">
        <p className="font-mono text-[0.72rem] font-semibold tracking-[0.16em] text-alert uppercase">
          {label}
        </p>
        <div className="mt-3 max-w-[64ch] space-y-3 text-ink-soft">
          {children}
        </div>
      </div>
    </aside>
  );
}
