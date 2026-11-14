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

---

# Response to reviewers (round 3)

All three reviewers recommended minor revision. Every MUST point was addressed. The SHOULD points were addressed except where stated. One finding (Reviewer 3, point 1) changed the pipeline, so **all numbers have been recomputed**. The headline result is unchanged in direction: within ±2 min, 16% for the timetable, 39% for the official real time and 64% for Bide+ (previously 16 / 41 / 67).

## Change that affects every number

**R3.1 Look-ahead in the choice of the Bide+ feed copy.** The comparison used to select the copy by the newest position inside it. Positions are published a median of 77 s after they are recorded (10th–90th percentile: 45–112 s). Bide+ could therefore use a copy downloaded after the query time *t*. The pipeline now uses only copies whose download time (taken from the file name) is at or before *t*, and at most 60 s before it. The text reports both ages: the copy is a median of 10 s old, and its positions about 1.5 min old (Section 5.1).

All pairs and the four ablation runs were rebuilt. Main set: 491,612 pairs.
- Below 3 min both sources are 90% within ±2 min (by-trip interval −0.7 to +0.3).
- At 3–6 / 6–10 / 10–20 / 20–30 min: official 59 / 42 / 30 / 23, Bide+ 80 / 74 / 62 / 48.

In the same change:
- The live entry is now keyed by vehicle as well as trip (R3.5). Trips served by two vehicles at once occurred on all days except Sunday.
- Queries after 23:00 are excluded from the coverage denominator and from the query counts (R3.4).

## Reviewer 1

1. **Coverage definition.** §6.1 now states the denominator: first-bus announcements with announced m < 30 (720,567). Of these, 533,549 (74.0%) were paired and 396,931 (55.1%) entered the main set. It explains that the main set also holds second-bus pairs and pairs announced at m ≥ 30. A new table gives coverage by announced minutes (Table A.2). The abstract and conclusions now say "first-bus announcements whose bus was tracked and confirmed".
2. **Unpaired announcements.** Coverage by announced minutes is reported (Table A.2). Accuracy on the paired-but-excluded pairs is also reported (Table A.3): the official real time was 42% within ±2 min when the bus was not in the feed and 40% when the identity was not confirmed, against 39% in the main set. The 26% that could not be paired cannot be evaluated, and the limitations now say the direction of any bias from them is unknown. Distributions by stop and line were not added.
3. **Limitations wording.** Now: "Pairs whose bus was not in the feed at *t* (15% of the paired ones) are excluded".
4. **"Narrowest interval".** Replaced by "the lowest lower bound, by stop at 3–6 minutes, is 14 points".
5. **Passenger ranking.** Restricted to missed buses. The text notes that with a one-minute margin the official real time gives a slightly longer expected wait than the timetable. It also gives the number of announcements used (353,392 of 401,356) and why the rest are dropped.
6. **Conservative intervals.** The abstract now quotes the by-stop interval. A bootstrap that resamples whole lines (73 lines) was added to §6.3: +16 to +36 points at 3–20 min, and −3.8 to +3.0 below 3 min. A two-way bootstrap was not added.
7. **Resample count.** Figure 2 now uses 2,000 resamples.
8. **Multiplicity.** The Figure 5 caption says the intervals are unadjusted. 56 of 59 stops remain significant after a Holm correction.
9. **GPS availability.** "99.7% of the eligible pairs". The text also says Table A.8 re-bins the pairs by the GPS-based passage (483,567 pairs).
10. **Structural zero.** Table 4 has a note explaining why the official Early share is zero at 0–2 min.
11. **Pairs per hour.** The caption now says 12,000 to 37,000.
12. **Zabalburu.** "Practically tie (35.5% and 35.1%)".
13. **Two random buses.** "Illustrate".
14. **Ablation.** Intervals were added. Removing the learned segment times lowers Bide+ by 29.0 to 30.7 points (by trip), leaving it 4–5 points below the official real time (by trip −5.0 to −3.8; by stop −6.0 to −2.9). Highlight 5 is kept, because the drop below the official source is significant.
15. **Change in coverage between rounds.** In round 1 the trip key used the trip number only. Bizkaibus reuses trip numbers within a day, so passages of different trips were merged and most were lost (22.7% paired). Round 2 identified trips by their full feed reference, which raised coverage to 74%. No inclusion rule was changed for that reason. The rules that were set after inspecting the data are now listed in §5.4 and §7.4.
16. **Atxuri.** §5.2 now says the exclusion was decided after inspecting the errors, and refers to the sensitivity row that keeps it.

## Reviewer 2

1. Passenger ranking: see R1.5.
2. Coverage: see R1.1.
3. **HTTP/HTTPS.** The paragraph now states facts only:
   - The plain-HTTP address stopped answering on 12 November at 17:12. From 13 November the capture used the HTTPS address of the same service.
   - 0.5% of requests failed over the week, all by timeout or a closed connection. No error status, rate-limit or blocking response was received.
   - The host serves no robots.txt, and no terms of use were found.
   - The inference "so there is no sign…" was deleted.
4. **Licence.** The raw official responses are stated to be outside the CC BY licence.
5. **Resample count.** See R1.7.
6. **Fallback layers.** One sentence was added: the bus was in the feed, but the GPS layer abstained.
7. **Highlight 4.** Now "Equal below 3 min; open-data method more often within ±2 min beyond". The abstract also says the official real time has the smaller mean error below 6 min.
8. **References.** All authors are listed (`maxbibnames=99`), dates are year-only, and access dates use ISO format. The companion paper has no DOI yet; it will be added when it is deposited.
9. **Floats among the references.** A page break was inserted before the bibliography, so the appendix now precedes the references.
10. **Length.** About 5,300 words of prose and 11 main-text tables and figures. The appendix can be moved to supplementary material if the editor prefers.
11. **Uncited claims in the Introduction.** "Most passengers" is now "Many passengers". "Launched in 2023" was removed.
12. **Recent ETA work.** Petersen et al. (2019, *Expert Systems with Applications*, verified on Crossref) is cited. The text says the comparison is with what the operator shows, not with the state of the art.
13. **Implication for operators.** A sentence on revising intermediate scheduled times, or holding at timing points, was added to §7.3.
14. **English and clarity.**
    - The sentence on stop selection was split in two.
    - The abstract now says "for the same buses at the same moments".
    - The first person was removed throughout.
    - "Official real time" is defined at first use and used consistently, including in the highlights.
15. **Keywords.** GTFS and SIRI are spelled out.

## Reviewer 3

1. **Look-ahead.** Fixed (see above).
2. **Matching.**
   - A table of accuracy by decile of the distance ratio was added (Table A.4). Bide+ is ahead in every decile, by 10 to 33 points.
   - Across stops, the Bide+ minus official gap does not depend on the share of matches rejected (correlation −0.05).
   - No target stop is visited twice by the same trip. 12 of the 60 stops are the last stop of some routes, and the effect of mismatches there is discussed in §5.3. A mismatch at a terminal stop would make the official error negative, the opposite of the bias observed.
   - The e1→0 consistency check was not implemented.
3. **Failed-passage rule.** The text now says the speed check uses the smaller of the feed distance and the official distance.
4. **Queries after 23:00.** Fixed.
5. **Live entry per vehicle.** Fixed.
6. **"Equal below three minutes".** Now "equally often within ±2 min". The abstract and highlights add that the official source has the smaller mean error below 6 min.
7. **Shared passage definition.** Stated in §7.4: the learned segment times were fitted on passages defined in the same way as the ground truth, so Bide+ is calibrated to that definition. The GPS-based passage shares the feed's vehicle-to-trip assignment and clock.
8. **Rules set after seeing the data.** Stated in §5.4 and §7.4.
9. **One passage per stop and trip.** No double visits exist among the target stops. Terminal stops are covered under point 2.
