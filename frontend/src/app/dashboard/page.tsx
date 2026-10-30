import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, AudioLines, Camera, Clock3, Languages } from "lucide-react";
import { Notice } from "@/components/ui/notice";
import { SessionGreeting } from "@/features/authentication/account-panel";

export const metadata: Metadata = { title: "Dashboard" };

const actions = [
  {
    href: "/translator/sign-to-speech",
    icon: Camera,
    title: "Sign to speech",
    description:
      "Open browser-local hand tracking. Spoken interpretation needs a compatible trained model, which is not bundled."
  },
  {
    href: "/translator/speech-to-sign",
    icon: AudioLines,
    title: "Speech to sign",
    description:
      "Type or record speech, review the transcript, and map exact verified-vocabulary matches."
  },
  {
    href: "/history",
    icon: Clock3,
    title: "Translation history",
    description: "Search and manage translations saved to your account."
  }
];

export default function DashboardPage() {
  return (
    <section className="page-container">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Your workspace</p>
          <h1>Welcome to SignLingo</h1>
          <SessionGreeting />
        </div>
        <Link className="button" href="/translator/speech-to-sign">
          Try speech to sign <ArrowRight aria-hidden="true" />
        </Link>
      </div>
      <Notice title="Limited translation preview">
        Account, history, and preferences APIs are connected. Speech-to-sign supports transcript
        review and exact vocabulary lookup; camera landmarks are processed in-browser. A trained
        recognition model, curated vocabulary, full ISL grammar, and signing animations are not
        bundled.
      </Notice>
      <div className="section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Quick actions</p>
            <h2>Choose a communication workflow.</h2>
          </div>
          <p>
            Review unsupported text carefully: exact vocabulary matching is not full ISL sentence
            translation.
          </p>
        </div>
        <div className="action-grid">
          {actions.map(({ href, icon: Icon, title, description }) => (
            <article className="card action-card" key={href}>
              <span className="action-icon">
                <Icon aria-hidden="true" />
              </span>
              <h2>{title}</h2>
              <p>{description}</p>
              <Link className="text-link" href={href}>
                Open workspace <ArrowRight aria-hidden="true" />
              </Link>
            </article>
          ))}
        </div>
      </div>
      <div className="workspace-grid">
        <section aria-labelledby="recent-heading" className="card empty-state">
          <div>
            <Clock3 aria-hidden="true" />
            <h2 id="recent-heading">Your recent translations</h2>
            <p>Nothing saved yet. Translations appear here after you explicitly save them.</p>
          </div>
        </section>
        <section aria-labelledby="language-heading" className="card workspace-panel">
          <div className="panel-heading">
            <div>
              <h2 id="language-heading">Language direction</h2>
              <p>Available language options</p>
            </div>
            <Languages aria-hidden="true" />
          </div>
          <p className="muted">Indian Sign Language ↔ Hindi · English</p>
          <p className="field-hint">Manage your saved language and accessibility preferences in Settings.</p>
        </section>
      </div>
    </section>
  );
}
