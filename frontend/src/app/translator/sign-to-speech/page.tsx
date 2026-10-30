import type { Metadata } from "next";
import { SignToSpeechExperience } from "@/features/sign-recognition/sign-to-speech-experience";

export const metadata: Metadata = { title: "Sign to speech" };

export default function SignToSpeechPage() {
  return (
    <section className="page-container">
      <div className="page-heading">
        <p className="eyebrow">Sign language translator</p>
        <h1>Sign to speech</h1>
        <p>
          Camera frames stay on your device. Recognition is experimental and needs a configured
          gesture model; when a label is available, choose when to speak it.
        </p>
      </div>
      <SignToSpeechExperience />
    </section>
  );
}
