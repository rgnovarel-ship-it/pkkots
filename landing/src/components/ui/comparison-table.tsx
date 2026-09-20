import type { Product, Row } from "@/data/novarel";

/* ==========================================================================
   Comparison Table — le comparatif des trois caméras.
   Un tableau de dossier technique : filets, pas d'ombres, pas d'arrondis.
   La colonne « meilleur choix » est la seule à porter le vert signal.
   Desktop : vrai <table>. Mobile : une fiche par produit, mêmes données.
   ========================================================================== */

function BestFlag({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 bg-signal px-2 py-1 font-mono text-[0.62rem] font-semibold tracking-[0.12em] text-ink uppercase">
      <svg viewBox="0 0 12 12" className="size-3" aria-hidden="true">
        <path d="M2 6.4 4.8 9 10 3.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {label}
    </span>
  );
}

function Criterion({ row }: { row: Row }) {
  return (
    <>
      <span className="block font-semibold">{row.criterion}</span>
      {row.hint && (
        <span className="mt-0.5 block text-[0.82rem] leading-snug text-muted">
          {row.hint}
        </span>
      )}
    </>
  );
}

export function ComparisonTable({
  products,
  rows,
  cta,
  ctaUrl,
}: {
  products: Product[];
  rows: Row[];
  cta: string;
  ctaUrl: string;
}) {
  return (
    <>
      {/* ---------- Desktop ---------- */}
      <div className="hidden md:block">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">
            Comparatif de trois caméras extérieures sans abonnement
          </caption>
          <thead>
            <tr>
              <th scope="col" className="w-[26%] align-bottom pb-5 pr-6">
                <span className="font-mono text-[0.7rem] font-semibold tracking-[0.16em] text-muted uppercase">
                  Critère
                </span>
              </th>
              {products.map((p) => (
                <th
                  key={p.id}
                  scope="col"
                  className={[
                    "w-[24.6%] border-t-2 px-5 pt-5 pb-5 align-bottom",
                    p.best
                      ? "border-t-signal-deep bg-surface"
                      : "border-t-line-strong",
                  ].join(" ")}
                >
                  <span className="flex min-h-6 items-center">
                    {p.best && p.bestLabel && <BestFlag label={p.bestLabel} />}
                  </span>
                  <span className="mt-3 block text-step-1 leading-tight font-bold">
                    {p.name}
                  </span>
                  <span className="mt-2 block font-mono text-[0.95rem] font-semibold text-ink">
                    {p.price}
                  </span>
                  <span className="mt-1 block font-mono text-[0.65rem] font-medium tracking-[0.12em] text-muted uppercase">
                    {p.priceNote}
                  </span>
                  <span className="mt-3 block max-w-[30ch] text-[0.88rem] leading-snug font-normal text-muted">
                    {p.summary}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.criterion} className="border-t border-line">
                <th scope="row" className="py-4 pr-6 align-top font-normal">
                  <Criterion row={row} />
                </th>
                {row.values.map((value, i) => (
                  <td
                    key={products[i].id}
                    className={[
                      "px-5 py-4 align-top text-[0.94rem] leading-snug",
                      products[i].best ? "bg-surface text-ink" : "text-ink-soft",
                    ].join(" ")}
                  >
                    {value}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-line">
              <td />
              {products.map((p) => (
                <td key={p.id} className={p.best ? "bg-surface px-5 pt-5 pb-6" : "px-5 pt-5 pb-6"}>
                  {p.best && (
                    <a
                      href={ctaUrl}
                      className="inline-flex w-full items-center justify-center gap-2 border border-signal-deep bg-signal px-4 py-3 text-[0.9rem] font-semibold text-ink no-underline transition-colors duration-150 ease-novarel hover:border-ink hover:bg-ink hover:text-paper"
                    >
                      {cta}
                    </a>
                  )}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>

      {/* ---------- Mobile ---------- */}
      <div className="space-y-6 md:hidden">
        {products.map((p, col) => (
          <article
            key={p.id}
            className={[
              "border-t-2 bg-surface p-5",
              p.best ? "border-t-signal-deep" : "border-t-line-strong",
            ].join(" ")}
          >
            {p.best && p.bestLabel && <BestFlag label={p.bestLabel} />}
            <h3 className="mt-3 text-step-1 leading-tight font-bold">{p.name}</h3>
            <p className="mt-2 font-mono font-semibold">
              {p.price}{" "}
              <span className="text-[0.65rem] font-medium tracking-[0.12em] text-muted uppercase">
                {p.priceNote}
              </span>
            </p>
            <p className="mt-2 text-[0.9rem] leading-snug text-muted">{p.summary}</p>

            <dl className="mt-5 border-t border-line">
              {rows.map((row) => (
                <div
                  key={row.criterion}
                  className="flex justify-between gap-6 border-b border-line py-3"
                >
                  <dt className="font-mono text-[0.68rem] font-medium tracking-[0.1em] text-muted uppercase">
                    {row.criterion}
                  </dt>
                  <dd className="max-w-[55%] text-right text-[0.9rem] leading-snug text-ink-soft">
                    {row.values[col]}
                  </dd>
                </div>
              ))}
            </dl>

            {p.best && (
              <a
                href={ctaUrl}
                className="mt-5 flex items-center justify-center gap-2 border border-signal-deep bg-signal px-4 py-3 text-[0.9rem] font-semibold text-ink no-underline"
              >
                {cta}
              </a>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
