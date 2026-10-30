import type { Metadata } from "next";
import { Notice } from "@/components/ui/notice";
import { HistoryList } from "@/features/translation-history/history-list";

export const metadata: Metadata = { title: "Translation history" };

export default function HistoryPage() {
  return (
    <section className="page-container">
      <div className="page-heading">
        <p className="eyebrow">Your translations</p>
        <h1>Translation history</h1>
        <p>Search and manage translations saved to your account.</p>
      </div>
      <Notice title="Only completed translations appear here">
        The history API is connected. Sign recognition and speech translation are still being
        developed, so this list may be empty until translations are available.
      </Notice>
      <HistoryList />
    </section>
  );
}
