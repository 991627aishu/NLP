# Demo script (≈8 minutes)

Start: `.\run.ps1` → open http://127.0.0.1:8000. Point at the **System status** chip first and say which backends are live
(e.g. "Neural MT: fallback active") — never demo a fallback as if it were IndicTrans2.

1. **English** — Ask: *What is the role of Agni in digestion?* Open **Sources & citations** (passage ID + page) and
   **How this was answered** (protected term Agni, backends, latency). Click the turmeric **Agni** chip → graph.
2. **Hindi** — Choose हिन्दी, tap a starter: *पित्त दोष के कार्य क्या हैं?* Show the trace: पित्त protected → *Pitta*.
   Note the badge: *English source text* (no neural MT) or *Machine-translated* (with IndicTrans2).
3. **Kannada with suffix** — ಕನ್ನಡ: *ಆಮ ದೋಷವನ್ನು ನಿವಾರಿಸುವುದು ಹೇಗೆ?* — trace shows ದೋಷವನ್ನು → Dosha (suffix stripped).
4. **Voice** (Chrome/Edge) — tap the mic (or Alt+M), say *What is Ojas?*, check the transcript, Ask; press **Read aloud**.
   Turn on *Conversation mode* in Research options to show the mic re-arming.
5. **Safety** — type *मुझे अचानक तेज़ सिरदर्द हो रहा है*: calm emergency card, read aloud automatically, no sources, no advice.
   Then *How many grams of Ashwagandha should I take daily?* → dose refusal.
6. **Knowledge graph** — search *ಪಿತ್ತ*; open the Pitta node: every link shows source + locator + review status.
   *Show the path* Tridosha → Ashwagandha. Toggle **List view**.
7. **Herbs** — search *अश्वगन्धा* → *Withania somnifera*: IMPPAT rows, Pharmacopoeia formulation, the "not evidence" note.
8. **Research lab** — Compare B0/B1/P1/P2 on the Kannada question; scroll to measured results: P1 − B1 CI includes 0;
   error analysis shows translation is the bottleneck. Say plainly what this means for the paper.
