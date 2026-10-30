import type { Metadata } from "next";
import { SpeechToSignComposer } from "@/features/translation/speech-to-sign-composer";

export const metadata: Metadata = { title: "Speech to sign" };

export default function SpeechToSignPage() {
  return <SpeechToSignComposer />;
}
