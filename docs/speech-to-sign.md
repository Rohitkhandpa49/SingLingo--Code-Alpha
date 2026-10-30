# Speech-to-sign flow

The speech-to-sign page combines the Phase 9 transcript review with an authenticated, exact-vocabulary lookup. Users can also type or edit text directly. Press **Prepare sign sequence** to send the chosen text and language (`auto`, `en`, or `hi`) to `POST /api/v1/isl/translate-text`. This endpoint returns a structured sequence of verified sign IDs and names, unsupported text spans, vocabulary version, and status. It does not write history.

Automatic language detection is limited to Latin/ASCII and Devanagari script cues. Mixed-script text requires an explicit language choice. Text and vocabulary values are Unicode-normalized and matched against exact reviewed `translation_texts` values. Longest exact phrase entries take precedence; duplicate mappings are reported as ambiguous. Unmatched text is listed with its normalized-string offsets. Input token and output sequence lengths are bounded.

This is a dictionary/phrase lookup, not an English-to-ISL translation model. It does not reorder English into ISL grammar or infer missing signs. A sequence assembled from multiple single-sign entries is marked partial with `sentence_grammar_unavailable`; only an exact verified sign or phrase mapping can be reported as successful. A missing vocabulary version returns no matches rather than fallback text.

After a successful mapping, the user may explicitly save the source text and ordered verified sign names to their authenticated translation history. It is not saved automatically. History remains subject to the existing account deletion and manual retention policies.

The page displays matched sign names and unsupported spans. Its 3D player only runs when every sequence item has a safely registered local GLB path and named animation clip. No such assets ship in this repository, so the sequence list is review-only and playback remains disabled. See [avatar asset registration](avatar-assets.md).
