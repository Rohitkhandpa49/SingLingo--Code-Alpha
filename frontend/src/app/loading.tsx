export default function Loading() {
  return (
    <section aria-label="Loading page" className="page-container" aria-busy="true">
      <div className="card empty-state">
        <p role="status">Loading SignLingo…</p>
      </div>
    </section>
  );
}
