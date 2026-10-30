import Link from "next/link";

export default function NotFound() {
  return (
    <section className="page-container">
      <div className="card empty-state">
        <div>
          <p className="eyebrow">404 · Page not found</p>
          <h1>We can’t find that page.</h1>
          <p>Check the address or return to the SignLingo home page.</p>
          <Link className="button" href="/" style={{ marginTop: "1rem" }}>
            Back to home
          </Link>
        </div>
      </div>
    </section>
  );
}
