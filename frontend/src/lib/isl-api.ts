import { apiRequest } from "@/lib/api";

export type ISLTextLanguage = "auto" | "en" | "hi";

export interface ISLTextSequenceItem {
  sign_id: string;
  sign_name: string;
  matched_text: string;
  animation_asset: string | null;
  animation_clip: string | null;
}

export interface ISLTextUnsupportedSegment {
  start_index: number;
  end_index: number;
  text: string;
  reason:
    | "language_not_detected"
    | "mixed_script_requires_language_selection"
    | "no_word_tokens"
    | "no_verified_mapping"
    | "ambiguous_verified_mapping"
    | "sentence_grammar_unavailable"
    | "input_token_limit_exceeded"
    | "sequence_limit_exceeded";
}

export interface ISLTextTranslationResponse {
  type: "isl_text_translation";
  translation_id: string;
  status: "success" | "partial" | "unsupported";
  source_text: string;
  normalized_text: string;
  language: "en" | "hi" | null;
  sequence: ISLTextSequenceItem[];
  unsupported_segments: ISLTextUnsupportedSegment[];
  translation_level: "single_sign" | "phrase" | "partial";
  vocabulary_version: string | null;
  sentence_grammar_available: false;
  timestamp: string;
}

export function translateTextToSigns(
  text: string,
  language: ISLTextLanguage
): Promise<ISLTextTranslationResponse> {
  return apiRequest<ISLTextTranslationResponse>("/isl/translate-text", {
    method: "POST",
    body: JSON.stringify({ text, language })
  });
}
