// Shown while a page waits for the backend (a cold pipeline run can take a
// few minutes; afterwards the backend cache answers instantly).
export default function Loading() {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-ink-2" role="status">
      <div className="h-1.5 w-40 overflow-hidden rounded-full bg-accent-soft/60">
        <div className="h-full w-1/3 animate-pulse rounded-full bg-accent" />
      </div>
      <p className="text-sm">Lade Daten … (beim ersten Abruf kann das ein paar Minuten dauern)</p>
    </div>
  );
}
