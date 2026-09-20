import { ShaderHero } from "@/components/ui/shader-hero";
import { AlertBanner } from "@/components/ui/alert-banner";
import { ComparisonTable } from "@/components/ui/comparison-table";
import {
  CTA_URL,
  alert,
  closing,
  footer,
  hero,
  products,
  rows,
} from "@/data/novarel";

/* Largeur de fer du site Flask : --shell = 74rem. */
const SHELL = "mx-auto w-full max-w-[74rem] px-[clamp(1.15rem,0.9rem+1.2vw,2.5rem)]";

function Wordmark({ tone }: { tone: "light" | "dark" }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg viewBox="0 0 24 24" className="size-6" aria-hidden="true" fill="none">
        <path
          d="M3.5 20V4l17 16V4"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="square"
          strokeLinejoin="miter"
        />
      </svg>
      <span className="text-[1.05rem] leading-none font-extrabold tracking-[0.02em]">
        NOVAREL
      </span>
      <span
        className={[
          "border-l pl-2 font-mono text-[0.6rem] font-medium tracking-[0.14em] uppercase",
          tone === "dark"
            ? "border-night-line text-night-muted"
            : "border-line-strong text-muted",
        ].join(" ")}
      >
        Sans abonnement
      </span>
    </span>
  );
}

function Hero() {
  return (
    <ShaderHero>
      <header className={`${SHELL} flex h-[60px] items-center text-night-ink`}>
        <Wordmark tone="dark" />
      </header>

      <div className={`${SHELL} pt-[clamp(4rem,10vh,7rem)] pb-[clamp(5rem,12vh,8rem)]`}>
        <p className="flex items-center gap-3 font-mono text-[0.7rem] font-medium tracking-[0.16em] text-night-muted uppercase">
          <span aria-hidden="true" className="h-px w-7 bg-night-line" />
          {hero.eyebrow}
        </p>

        <h1 className="mt-7 max-w-[16ch] text-step-5 leading-[0.98] font-extrabold tracking-[-0.03em] text-night-ink text-balance">
          {hero.titleLines[0]}
          <br />
          {hero.titleLines[1]}
        </h1>

        <p className="mt-8 max-w-[58ch] text-step-1 leading-relaxed text-night-muted">
          {hero.subtitle[0]}
          <br className="hidden sm:block" />{" "}
          <span className="text-night-ink/85">{hero.subtitle[1]}</span>
        </p>

        <div className="mt-11 flex flex-wrap items-center gap-x-8 gap-y-4">
          <a
            href={CTA_URL}
            className="inline-flex items-center gap-2.5 border border-signal-deep bg-signal px-6 py-3.5 text-[0.95rem] font-semibold text-ink no-underline transition-colors duration-150 ease-novarel hover:border-night-ink hover:bg-night-ink hover:text-night-paper"
          >
            {hero.cta}
            <svg viewBox="0 0 16 16" className="size-4" aria-hidden="true" fill="none">
              <path d="M2 8h11M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="square" />
            </svg>
          </a>
          <a
            href="#comparatif"
            className="font-mono text-[0.72rem] font-medium tracking-[0.14em] text-night-muted uppercase underline decoration-night-line underline-offset-[6px] transition-colors duration-150 hover:text-night-ink"
          >
            {hero.scrollHint}
          </a>
        </div>
      </div>
    </ShaderHero>
  );
}

export function Page() {
  return (
    <>
      <Hero />

      <main className="novarel-grid">
        {/* ---------- Avertissement consommateur ---------- */}
        <section className={`${SHELL} pt-[clamp(3.5rem,8vw,6rem)]`}>
          <AlertBanner label={alert.label}>
            {alert.body.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </AlertBanner>
        </section>

        {/* ---------- Comparatif ---------- */}
        <section
          id="comparatif"
          className={`${SHELL} scroll-mt-8 pt-[clamp(4.5rem,10vw,8rem)]`}
        >
          <p className="flex items-center gap-3 font-mono text-[0.7rem] font-medium tracking-[0.16em] text-muted uppercase">
            <span aria-hidden="true" className="h-px w-7 bg-line-strong" />
            Le comparatif
          </p>
          <h2 className="mt-6 max-w-[20ch] text-step-3 leading-[1.05] font-bold tracking-[-0.02em] text-balance">
            Trois caméras extérieures qui fonctionnent sans abonnement.
          </h2>
          <p className="mt-5 max-w-[56ch] text-step-1 text-muted">
            Mêmes critères pour les trois. Les prix sont constatés et payés une
            seule fois.
          </p>

          <div className="mt-12">
            <ComparisonTable
              products={products}
              rows={rows}
              cta="Voir le comparatif"
              ctaUrl={CTA_URL}
            />
          </div>

          <p className="mt-6 font-mono text-[0.68rem] font-medium tracking-[0.12em] text-muted uppercase">
            {footer.note}
          </p>
        </section>

        {/* ---------- Signature ---------- */}
        <section className={`${SHELL} pt-[clamp(5rem,12vw,9rem)] pb-[clamp(4rem,9vw,7rem)]`}>
          <div className="border-t border-line pt-12">
            <p className="max-w-[24ch] text-step-3 leading-[1.1] font-extrabold tracking-[-0.02em] text-balance">
              {closing.signature}
            </p>
            <p className="mt-6 max-w-[58ch] text-step-1 text-muted">
              {closing.body}
            </p>
            <a
              href={CTA_URL}
              className="mt-9 inline-flex items-center gap-2.5 border border-ink bg-ink px-6 py-3.5 text-[0.95rem] font-semibold text-paper no-underline transition-colors duration-150 ease-novarel hover:border-signal-deep hover:bg-signal hover:text-ink"
            >
              {closing.cta}
              <svg viewBox="0 0 16 16" className="size-4" aria-hidden="true" fill="none">
                <path d="M2 8h11M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="square" />
              </svg>
            </a>
          </div>
        </section>
      </main>

      <footer className="border-t border-line bg-surface">
        <div className={`${SHELL} flex flex-col gap-6 py-10 sm:flex-row sm:items-start sm:justify-between`}>
          <Wordmark tone="light" />
          <p className="max-w-[54ch] text-[0.85rem] leading-relaxed text-muted">
            {footer.disclosure}
          </p>
        </div>
      </footer>
    </>
  );
}
