Model-selection priority:



* Risk separation / ranking: prioritize top-10 lift, top-10 capture, and top-20 capture.
* OOT stability: separation should persist across individual validation years, not just pooled data.
* Risk shape: observed frequency/AAL should generally increase across predicted-risk deciles, especially in the upper tail.
* Calibration: predicted magnitude should match observed magnitude overall and across deciles, but calibration can be corrected after selecting a strong ranking model.
* Secondary metrics: AUC, average precision, group MAE, etc. are supporting diagnostics, not the primary selection criteria.



For frequency models, I’d be even more explicit:



Frequency model: optimize ranking first. Primary metrics are top-10 claim lift/capture and top-20 claim capture. Require reasonable year-to-year OOT stability and sensible observed claim-frequency deciles. Calibration of absolute probabilities is secondary.



For the final AAL model:



AAL model: prioritize loss separation first, using top-10/top-20 loss capture and lift. Then check that observed AAL increases sensibly through risk deciles. After ranking is satisfactory, evaluate and correct calibration using predicted-vs-observed AAL by decile and overall.



The key sentence for me in future runs would be:



“Do not choose a model because it has lower prediction error if that comes at a meaningful loss of risk separation. Prefer strong, stable ranking first, then calibrate the magnitude.”



I’d still treat obviously bad shape as a guardrail. We don't want a model with amazing top-decile lift but nonsensical behavior everywhere else. The goal is strong separation plus a credible risk curve, then calibration.

