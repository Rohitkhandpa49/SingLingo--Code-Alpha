import type { Metadata } from "next";
import Link from "next/link";
import { Accessibility, ArrowRight, HandHeart, ShieldCheck } from "lucide-react";

export const metadata: Metadata = { title: "About SignLingo" };

const principles = [
  {
    icon: Accessibility,
    title: "Accessibility is foundational",
    body: "Keyboard use, clear labels, readable contrast, responsive layouts, and reduced motion belong in the product from the start."
  },
  {
    icon: HandHeart,
    title: "Respect language and community",
    body: "ISL is a rich, natural language. Recognition coverage and signing assets need appropriate data, community-informed review, and careful evaluation."
  },
  {
    icon: ShieldCheck,
    title: "Privacy and honest limits",
    body: "Camera and microphone access must be user-controlled. Uncertain output should be labeled as uncertain, and raw recordings should not be stored by default."
  }
];

export default function AboutPage() {
  return (
    <section className="page-container">
      <div className="page-heading">
        <p className="eyebrow">About the project</p>
        <h1>Communication tools built with care.</h1>
        <p>
          SignLingo is a work in progress exploring how software can support conversations
          between Deaf and hearing people in India.
        </p>
      </div>
      <div className="feature-grid">
        {principles.map(({ icon: Icon, title, body }) => (
          <article className="card feature-card" key={title}>
            <span className="feature-icon">
              <Icon aria-hidden="true" />
            </span>
            <h2>{title}</h2>
            <p>{body}</p>
          </article>
        ))}
      </div>
      <div className="section">
        <div className="split-panel">
          <div>
            <p className="eyebrow">Current status</p>
            <h2>The interface is ahead of the translation engine.</h2>
            <p className="muted">
              This frontend does not currently recognize signs, transcribe speech, or generate
              sign animations. Those capabilities require tested backend and AI components.
            </p>
          </div>
          <div>
            <p className="muted">
              The project aims to support SDG 3 (Good Health and Well-Being) and SDG 10 (Reduced
              Inequalities). This is an assistive communication project, not a replacement for
              qualified interpreters or a guarantee of accurate translation.
            </p>
            <Link className="text-link" href="/translator/sign-to-speech">
              Explore the interface <ArrowRight aria-hidden="true" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
