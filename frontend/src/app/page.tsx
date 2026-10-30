"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import {
  Accessibility,
  ArrowRight,
  AudioLines,
  Camera,
  Hand,
  Languages,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import { Notice } from "@/components/ui/notice";

const features = [
  {
    icon: Camera,
    title: "Sign to speech",
    description:
      "Hand tracking runs in your browser. Spoken interpretation requires a compatible recognition model and reviewed vocabulary, which are not bundled."
  },
  {
    icon: AudioLines,
    title: "Speech to sign",
    description:
      "Record Hindi or English speech, review its transcript, or type text. Only exact verified-vocabulary matches are mapped; full ISL grammar and animations are not included."
  },
  {
    icon: Accessibility,
    title: "Designed for access",
    description:
      "Readable layouts, keyboard-friendly controls, responsive screens, and reduced-motion support are part of the foundation."
  }
];

export default function HomePage() {
  const reducedMotion = useReducedMotion();

  return (
    <>
      <section className="page-container hero" aria-labelledby="hero-title">
        <motion.div
          animate={reducedMotion ? undefined : { opacity: 1, y: 0 }}
          initial={reducedMotion ? false : { opacity: 0, y: 12 }}
          transition={reducedMotion ? { duration: 0 } : { duration: 0.45 }}
        >
          <p className="eyebrow">
            <Sparkles aria-hidden="true" size={15} /> Communication without barriers
          </p>
          <h1 id="hero-title">
            Every conversation deserves <span>to be understood.</span>
          </h1>
          <p className="hero-copy">
            SignLingo offers carefully scoped communication workflows for Indian Sign Language
            and spoken Hindi or English, with clear limits on what is verified today.
          </p>
          <div className="hero-actions">
            <Link className="button" href="/translator/speech-to-sign">
              Try speech to sign <ArrowRight aria-hidden="true" />
            </Link>
            <Link className="button button-secondary" href="/translator/sign-to-speech">
              Explore sign input
            </Link>
            <Link className="button button-secondary" href="/about">
              How it works
            </Link>
          </div>
          <p className="hero-note">
            <ShieldCheck aria-hidden="true" />
            Camera frames stay in your browser; audio is temporary and history is opt-in.
          </p>
        </motion.div>
        <motion.div
          aria-label="Illustration of a person communicating with expressive hands"
          className="hero-art"
          initial={reducedMotion ? false : { opacity: 0, scale: 0.97 }}
          role="img"
          transition={reducedMotion ? { duration: 0 } : { duration: 0.55, delay: 0.1 }}
          animate={reducedMotion ? undefined : { opacity: 1, scale: 1 }}
        >
          <div aria-hidden="true" className="hero-orbit" />
          <div aria-hidden="true" className="hero-person">
            <span className="hero-person-face" />
          </div>
          <div aria-hidden="true" className="hero-chip hero-chip-top">
            <Hand /> ISL
          </div>
          <div aria-hidden="true" className="hero-chip hero-chip-bottom">
            <Languages /> Hindi · English
          </div>
        </motion.div>
      </section>

      <section aria-label="Project status" className="page-container">
        <Notice title="Limited preview — complete ISL translation is not available">
          You can review Hindi/English transcripts and map exact verified vocabulary where entries
          are configured; camera landmarks stay browser-local. This build includes no trained
          recognition model, curated vocabulary, ISL sentence grammar, or validated signing
          animations.
        </Notice>
      </section>

      <section className="page-container section" id="features">
        <div className="section-header">
          <div>
            <p className="eyebrow">Built with care</p>
            <h2>Technology should support communication, not overpromise it.</h2>
          </div>
          <p>
            SignLingo is being developed in small, testable steps with an emphasis on honest
            recognition, privacy, and accessible interactions.
          </p>
        </div>
        <div className="feature-grid">
          {features.map(({ icon: Icon, title, description }) => (
            <article className="card feature-card" key={title}>
              <span className="feature-icon">
                <Icon aria-hidden="true" />
              </span>
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="page-container section" id="how-it-works">
        <div className="split-panel">
          <div>
            <p className="eyebrow">A careful approach</p>
            <h2>Useful tools start with trust.</h2>
            <p className="muted">
              ISL is a full language, not a set of interchangeable hand poses. Recognition and
              animations need suitable data, evaluation, and review before they can be presented
              as reliable translations.
            </p>
            <Link className="text-link" href="/about">
              Read our principles <ArrowRight aria-hidden="true" />
            </Link>
          </div>
          <ol className="step-list">
            <li>
              <span className="step-number">1</span>
              <span>Capture input only with clear permission and user control.</span>
            </li>
            <li>
              <span className="step-number">2</span>
              <span>Use evaluated models and show uncertainty when confidence is low.</span>
            </li>
            <li>
              <span className="step-number">3</span>
              <span>Map output to reviewed language and animation assets.</span>
            </li>
          </ol>
        </div>
      </section>
    </>
  );
}
