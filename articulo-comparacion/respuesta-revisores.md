# Response to reviewers (round 1)

Manuscript: *Accuracy of open-data versus operator real-time bus arrival predictions: a paired evaluation of the Bide+ method in Biscay, Spain*

Both reviewers recommended major revision. All points have been addressed except where stated. Numbers refer to the revised manuscript.

## Reviewer 1 (methodology and statistics)

**M1. Matching and gross mismatches.** Each match is now confirmed with the distance the official service reports for the announced bus, compared with the along-route distance of the matched bus in the feed (within 500 m or between 0.6 and 2 times; Section 5.3). Announcements that fail are excluded and counted (Table 2). Stricter and absent checks are in the sensitivity table (Table 12). The text now describes the rule exactly as the code applies it (candidates are buses tracked in the feed). The `tipo` field was empty in every response and is reported as such (Section 3.2). Continuity across queries was not added; the distance check addresses the same failure.

**M2. Ground truth from the same feed.** The "shared and favours neither" wording is removed. The passage is shifted by ±30 and ±60 s in the sensitivity analysis (Table 12). Failed reconstructions are screened with a physical rule (more than 30 m/s from the reported distance; 0.6% of pairs), and Atxuri (3394) is excluded with its reason (Section 5.2, `dias.json`). An independent field validation was not possible within this revision and is stated as a limitation (Section 7.4).

**M3. Selection and the 19%.** A flow table by day (Table 2) and the coverage figures (22.7% paired, 16.3% in the main analysis, of next-bus announcements under 30 min) are reported in Section 6.1 and the limitations. When Bide+ has no live position, its fallback prediction is now computed instead of dropping the case; these pairs are in a sensitivity analysis (Table 12). Inverse-probability weighting was not attempted.

**M4. Horizon defined by the outcome.** Results by announced waiting time are added (Table 6, Section 6.4).

**M5. Time and rounding.** Official truncation (+30 s) and Bide+ in seconds and truncated are in Table 12. Bide+ now uses the app's rounding (halves away from zero). Snapshot age (median 28 s) and response latency (median 0.9 s) are reported.

**M6. Stop selection.** The selection rule is described (Section 4.2), and results without the priority stops are given (Tables 9 and 12).

**M7. Inference.** 2,000 bootstrap resamples, clustered by trip and, separately, by stop, and a cluster-robust paired test of the absolute error (Diebold–Mariano style) are in Table 5. One pair per passage is in Table 12. "58 of 59 stops" is complemented with the number of stops whose interval excludes zero (56). A mixed-effects model was not fitted; the two clusterings and the test cover the dependence.

**M8. Days and composition.** Saturday 14 is explained (to be added in the next version), "Weekend" is now "Sunday", "every day of the week" is removed, and the evening drop in pairs is explained (Section 6.8).

**M9. Replay versus production.** "Reproduces exactly" is now "agrees on all 407 test vectors"; the production engine is stated to be private. "Conservative estimate" is removed. ±1 and ±3 thresholds, mean absolute error and a cumulative distribution are added. The study is stated not to be preregistered, and a confirmatory replication is called for.

**M10. Conflict of interest and framing.** A declaration of competing interest is added. Speculation about the operator's algorithm is removed. Section 7.2 is now "Possible explanations", supported by an ablation (Table 11: Bide+ without learned segment times falls below the official real time). Conclusions are limited to the network, week and stops.

**M11. Passenger impact.** A passenger decision model is added (Section 5.4, Table 8), and "Early" is described statistically elsewhere.

**M12. Provenance.** The number of duplicated-line exclusions is reported (none). Whether the web service equals the app display was not verified independently and is implicit in the description.

**Minor points.** All addressed: 60 stops "of which 28 priority"; ±1 and signed medians (Table 4); sign convention repeated in captions; Figure 6 axes and legends; Figure 5 marker size by n; Figure 3 replaced by a cumulative distribution and a signed histogram with tail masses in the caption; examples now drawn at random (fixed seed), two from the whole network and one per direction at San Juan (Amorebieta); abstract intervals quoted per horizon; key-results box replaced by highlights; notation defined in Section 5.1.

## Reviewer 2 (domain and publication norms)

**Literature.** Related work moved to Section 2 and expanded with primary AVL prediction works (Lin and Zeng; Cathey and Dailey; Shalaby and Farhan; Jeong and Rilett; Vanajakshi et al.; Chien et al.; Yu et al.; Mazloumi et al.), passenger impact (Dziekan and Kottenhoff; Ferris et al.; Tang and Thakuriah; Brakewood et al. 2015) and forecast comparison (Diebold and Mariano; Gneiting). All checked against Crossref.

**Shared ground truth, matching, selection, quantisation, inference, missing Saturday, zero-accuracy stop, aggregate figures.** See Reviewer 1, M1–M8. Horizon-stratified results are now the main presentation.

**Unsupported claims and tone.** "Makes passengers miss the bus" replaced by the passenger model; "every day of the week" removed; "conservative estimate" removed; Section 7.2 hedged and supported by ablation; policy recommendation replaced by the case for operators publishing predictions for independent audit; footnote with the app URL removed; examples drawn at random.

**Norms.** Highlights (5 bullets, ≤85 characters); keywords reduced to 7; abstract 250 words with limitations; declarations of competing interest, funding, CRediT, data availability, and data collection and terms of use added; affiliation and e-mail in elsarticle fields; `uniquename=false`; CEN standard in English; roadmap includes all sections. The generative-AI declaration is left to the author's final version. Line numbers and double spacing (`review` option) will be set at submission.

**Not done.** Contacting the operator for a right of reply; field validation of the passage; logging the live app.
