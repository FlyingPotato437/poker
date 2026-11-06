# Event simulation

Truth model from 10800 SNGs, knowledge model from 10800 (disjoint halves). 10k-SNG score noise sd = 1.03% of fair. Scores are weighted x-fair (weights 1..6)/21.

Model check (additive model vs each scenario's direct mean, half A): max |level error|, max |error of gain vs cand|, argmax direct / model:

| scenario | level err | gain err | best direct | best model |
|---|---|---|---|---|
| std_tag | 2.6% | 1.5% | cand | cand |
| llm_heavy | 3.0% | 1.9% | c_value | c_value |
| jammer_heavy | 2.3% | 1.0% | cand | cand |
| station_heavy | 1.3% | 1.8% | r2p0 | r2p0 |
| nit_heavy | 1.1% | 1.0% | c_value | c_value |
| maniac_heavy | 1.5% | 0.3% | r2p0 | r2p0 |
| prepped_heavy | 1.8% | 2.1% | x | x |
| broken_heavy | 1.7% | 1.4% | cand | cand |
| realistic | 6.3% | 4.8% | cand | cand |
| strong_mixed | 3.7% | 6.9% | r2p0 | cand |
| github_heavy | 3.8% | 4.0% | c_value | c_value |
| github_tough | 3.5% | 3.4% | cand | cand |
| event_like | 7.8% | 4.6% | xex2 | xex2 |
| event_like_prep | 7.9% | 5.2% | c_value | xex2 |
| uniform | 12.6% | 8.8% | c_steal | cand |

Truth-model x-fair per named scenario (all records; this is the matrix the event sim plays on):

| scenario | cand | ev_t4 | x | xex2 | s5p0 | r2p0 | c_calldown | c_value | c_steal | best | best − cand |
|---|---|---|---|---|---|---|---|---|---|---|---|
| std_tag | 1.604 | 1.430 | 1.480 | 1.514 | 1.516 | 1.577 | 1.583 | 1.568 | 1.620 | c_steal | +1.6% |
| llm_heavy | 2.096 | 1.899 | 1.995 | 1.992 | 1.988 | 2.044 | 2.012 | 2.092 | 2.079 | cand | +0.0% |
| jammer_heavy | 2.053 | 1.908 | 1.972 | 1.971 | 1.961 | 2.001 | 2.018 | 2.053 | 2.067 | c_steal | +1.5% |
| station_heavy | 2.326 | 2.215 | 2.343 | 2.314 | 2.303 | 2.395 | 2.165 | 2.338 | 2.316 | r2p0 | +6.9% |
| nit_heavy | 2.007 | 1.769 | 1.919 | 1.918 | 1.871 | 1.963 | 1.924 | 2.042 | 2.031 | c_value | +3.5% |
| maniac_heavy | 2.090 | 2.029 | 2.075 | 2.094 | 2.085 | 2.118 | 2.044 | 2.093 | 2.087 | r2p0 | +2.7% |
| prepped_heavy | 1.059 | 1.044 | 1.053 | 1.033 | 1.041 | 1.003 | 1.027 | 1.037 | 0.958 | cand | +0.0% |
| broken_heavy | 2.302 | 2.088 | 2.217 | 2.257 | 2.192 | 2.255 | 2.231 | 2.261 | 2.280 | cand | +0.0% |
| realistic | 1.669 | 1.509 | 1.565 | 1.603 | 1.584 | 1.620 | 1.629 | 1.649 | 1.638 | cand | +0.0% |
| zoo_default | 2.315 | 2.150 | 2.242 | 2.260 | 2.245 | 2.295 | 2.256 | 2.308 | 2.312 | cand | +0.0% |
| rival_mid | 1.984 | 1.771 | 1.863 | 1.935 | 1.852 | 1.874 | 1.875 | 1.974 | 2.016 | c_steal | +3.2% |
| strong_mixed | 1.431 | 1.320 | 1.336 | 1.391 | 1.362 | 1.387 | 1.394 | 1.396 | 1.375 | cand | +0.0% |
| github_heavy | 2.242 | 2.082 | 2.204 | 2.181 | 2.196 | 2.225 | 2.230 | 2.261 | 2.228 | c_value | +1.9% |
| github_tough | 2.295 | 2.207 | 2.245 | 2.245 | 2.216 | 2.285 | 2.272 | 2.283 | 2.293 | cand | +0.0% |
| event_like | 1.505 | 1.374 | 1.455 | 1.489 | 1.423 | 1.441 | 1.466 | 1.461 | 1.434 | cand | +0.0% |
| event_like_prep | 1.457 | 1.336 | 1.408 | 1.443 | 1.378 | 1.390 | 1.411 | 1.415 | 1.373 | cand | +0.0% |

### main: practice 1000 hands, bias sd 5%, drift 8%/step (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.8730 | 1.3713 | +0.00 ±0.00 | +0.00 | +0.00 | 0.52 |
| b_fixed_ev_t4 | 1.7262 | 1.2741 | -14.69 ±0.09 | -21.82 | -24.89 | 15.21 |
| c_handoff_rule | 1.8720 | 1.3645 | -0.10 ±0.01 | +0.00 | -10.62 | 0.63 |
| c2_bayes_L1 | 1.8724 | 1.3702 | -0.06 ±0.01 | -0.53 | -4.86 | 0.59 |
| d_classifier_L2 | 1.8677 | 1.3705 | -0.53 ±0.03 | -3.42 | -10.38 | 1.05 |
| d3_classifier_L2_m3 | 1.8711 | 1.3705 | -0.20 ±0.02 | -1.70 | -10.15 | 0.72 |
| d2_centroid_L2 | 1.8621 | 1.3695 | -1.09 ±0.03 | -4.28 | -6.33 | 1.62 |
| e_explore_L1 | 1.8713 | 1.3688 | -0.17 ±0.01 | -0.56 | -5.24 | 0.70 |
| g_bayes_L1+L2 | 1.8707 | 1.3678 | -0.23 ±0.02 | -2.26 | -5.81 | 0.76 |
| h_station_rule_L2 | 1.8744 | 1.3713 | +0.14 ±0.02 | +0.00 | -0.28 | 0.39 |
| f_oracle | 1.8783 | 1.3752 | +0.52 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -0.8 event_like +0.0 event_like_prep -0.0 github_heavy +0.4 github_tough -0.7 jammer_heavy +0.0 llm_heavy +0.0 maniac_heavy +0.0 nit_heavy +0.0 prepped_heavy -0.4 random -0.0 realistic +0.0 rival_mid -0.0 station_heavy -0.2 std_tag +0.0 strong_mixed -0.0 zoo_default -0.2, d_classifier_L2: broken_heavy -0.8 event_like -0.0 event_like_prep -0.0 github_heavy +0.6 github_tough -3.5 jammer_heavy -0.7 llm_heavy +0.0 maniac_heavy -1.4 nit_heavy +0.2 prepped_heavy -0.6 random -0.5 realistic -0.5 rival_mid -0.5 station_heavy +0.6 std_tag -1.2 strong_mixed -0.6 zoo_default -0.4, g_bayes_L1+L2: broken_heavy +0.0 event_like +0.0 event_like_prep +0.0 github_heavy +0.1 github_tough -4.0 jammer_heavy -0.6 llm_heavy +0.0 maniac_heavy -1.0 nit_heavy +0.5 prepped_heavy -0.4 random -0.2 realistic -0.0 rival_mid -0.1 station_heavy +1.8 std_tag -0.5 strong_mixed -0.0 zoo_default -0.0, f_oracle: broken_heavy +0.0 event_like +0.8 event_like_prep +0.9 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.0 llm_heavy +0.3 maniac_heavy +2.4 nit_heavy +1.1 prepped_heavy +1.2 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.3 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### no practice, bias sd 5% (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.8730 | 1.3713 | +0.00 ±0.00 | +0.00 | +0.00 | 0.52 |
| b_fixed_ev_t4 | 1.7262 | 1.2741 | -14.69 ±0.09 | -21.82 | -24.89 | 15.21 |
| c_handoff_rule | 1.8720 | 1.3645 | -0.10 ±0.01 | +0.00 | -10.62 | 0.63 |
| c2_bayes_L1 | 1.8724 | 1.3702 | -0.06 ±0.01 | -0.53 | -4.86 | 0.59 |
| d_classifier_L2 | 1.8677 | 1.3705 | -0.53 ±0.03 | -3.37 | -10.15 | 1.05 |
| d3_classifier_L2_m3 | 1.8710 | 1.3705 | -0.20 ±0.02 | -1.73 | -10.15 | 0.72 |
| d2_centroid_L2 | 1.8626 | 1.3695 | -1.04 ±0.03 | -4.14 | -6.03 | 1.57 |
| e_explore_L1 | 1.8713 | 1.3688 | -0.17 ±0.01 | -0.56 | -5.24 | 0.70 |
| g_bayes_L1+L2 | 1.8713 | 1.3678 | -0.18 ±0.02 | -1.80 | -5.53 | 0.70 |
| h_station_rule_L2 | 1.8743 | 1.3713 | +0.13 ±0.01 | +0.00 | +0.00 | 0.40 |
| f_oracle | 1.8783 | 1.3752 | +0.52 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -0.8 event_like +0.0 event_like_prep -0.0 github_heavy +0.4 github_tough -0.7 jammer_heavy +0.0 llm_heavy +0.0 maniac_heavy +0.0 nit_heavy +0.0 prepped_heavy -0.4 random -0.0 realistic +0.0 rival_mid -0.0 station_heavy -0.2 std_tag +0.0 strong_mixed -0.0 zoo_default -0.2, d_classifier_L2: broken_heavy -0.8 event_like -0.0 event_like_prep -0.0 github_heavy +0.5 github_tough -3.4 jammer_heavy -0.7 llm_heavy +0.0 maniac_heavy -1.4 nit_heavy +0.2 prepped_heavy -0.6 random -0.5 realistic -0.5 rival_mid -0.5 station_heavy +0.3 std_tag -1.2 strong_mixed -0.6 zoo_default -0.4, g_bayes_L1+L2: broken_heavy +0.0 event_like +0.0 event_like_prep +0.0 github_heavy +0.1 github_tough -3.1 jammer_heavy -0.5 llm_heavy +0.0 maniac_heavy -1.0 nit_heavy +0.5 prepped_heavy -0.4 random -0.1 realistic -0.0 rival_mid -0.1 station_heavy +1.4 std_tag -0.4 strong_mixed -0.0 zoo_default -0.0, f_oracle: broken_heavy +0.0 event_like +0.8 event_like_prep +0.9 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.0 llm_heavy +0.3 maniac_heavy +2.4 nit_heavy +1.1 prepped_heavy +1.2 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.3 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### practice 200 hands (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.8730 | 1.3713 | +0.00 ±0.00 | +0.00 | +0.00 | 0.52 |
| b_fixed_ev_t4 | 1.7262 | 1.2741 | -14.69 ±0.09 | -21.82 | -24.89 | 15.21 |
| c_handoff_rule | 1.8720 | 1.3645 | -0.10 ±0.01 | +0.00 | -10.62 | 0.63 |
| c2_bayes_L1 | 1.8724 | 1.3702 | -0.06 ±0.01 | -0.53 | -4.86 | 0.59 |
| d_classifier_L2 | 1.8677 | 1.3705 | -0.53 ±0.03 | -3.39 | -10.38 | 1.06 |
| d3_classifier_L2_m3 | 1.8710 | 1.3705 | -0.20 ±0.02 | -1.73 | -10.15 | 0.72 |
| d2_centroid_L2 | 1.8621 | 1.3694 | -1.09 ±0.03 | -4.25 | -6.14 | 1.61 |
| e_explore_L1 | 1.8713 | 1.3688 | -0.17 ±0.01 | -0.56 | -5.24 | 0.70 |
| g_bayes_L1+L2 | 1.8710 | 1.3678 | -0.20 ±0.02 | -2.00 | -5.80 | 0.73 |
| h_station_rule_L2 | 1.8743 | 1.3713 | +0.13 ±0.02 | +0.00 | -0.28 | 0.39 |
| f_oracle | 1.8783 | 1.3752 | +0.52 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -0.8 event_like +0.0 event_like_prep -0.0 github_heavy +0.4 github_tough -0.7 jammer_heavy +0.0 llm_heavy +0.0 maniac_heavy +0.0 nit_heavy +0.0 prepped_heavy -0.4 random -0.0 realistic +0.0 rival_mid -0.0 station_heavy -0.2 std_tag +0.0 strong_mixed -0.0 zoo_default -0.2, d_classifier_L2: broken_heavy -0.8 event_like -0.0 event_like_prep -0.0 github_heavy +0.6 github_tough -3.5 jammer_heavy -0.7 llm_heavy +0.0 maniac_heavy -1.4 nit_heavy +0.2 prepped_heavy -0.6 random -0.5 realistic -0.5 rival_mid -0.5 station_heavy +0.3 std_tag -1.2 strong_mixed -0.6 zoo_default -0.4, g_bayes_L1+L2: broken_heavy +0.0 event_like +0.0 event_like_prep +0.0 github_heavy +0.1 github_tough -3.5 jammer_heavy -0.5 llm_heavy +0.0 maniac_heavy -1.0 nit_heavy +0.5 prepped_heavy -0.4 random -0.1 realistic -0.0 rival_mid -0.1 station_heavy +1.6 std_tag -0.4 strong_mixed -0.0 zoo_default -0.0, f_oracle: broken_heavy +0.0 event_like +0.8 event_like_prep +0.9 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.0 llm_heavy +0.3 maniac_heavy +2.4 nit_heavy +1.1 prepped_heavy +1.2 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.3 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### practice full log (10k SNGs) (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.8730 | 1.3713 | +0.00 ±0.00 | +0.00 | +0.00 | 0.52 |
| b_fixed_ev_t4 | 1.7262 | 1.2741 | -14.69 ±0.09 | -21.82 | -24.89 | 15.21 |
| c_handoff_rule | 1.8720 | 1.3645 | -0.10 ±0.01 | +0.00 | -10.62 | 0.63 |
| c2_bayes_L1 | 1.8724 | 1.3702 | -0.06 ±0.01 | -0.53 | -4.86 | 0.59 |
| d_classifier_L2 | 1.8675 | 1.3705 | -0.55 ±0.03 | -3.52 | -10.65 | 1.07 |
| d3_classifier_L2_m3 | 1.8710 | 1.3705 | -0.20 ±0.02 | -1.81 | -10.65 | 0.73 |
| d2_centroid_L2 | 1.8621 | 1.3695 | -1.09 ±0.03 | -4.28 | -6.33 | 1.62 |
| e_explore_L1 | 1.8713 | 1.3688 | -0.17 ±0.01 | -0.56 | -5.24 | 0.70 |
| g_bayes_L1+L2 | 1.8704 | 1.3678 | -0.26 ±0.02 | -2.52 | -5.89 | 0.79 |
| h_station_rule_L2 | 1.8744 | 1.3713 | +0.14 ±0.02 | +0.00 | +0.00 | 0.39 |
| f_oracle | 1.8783 | 1.3752 | +0.52 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -0.8 event_like +0.0 event_like_prep -0.0 github_heavy +0.4 github_tough -0.7 jammer_heavy +0.0 llm_heavy +0.0 maniac_heavy +0.0 nit_heavy +0.0 prepped_heavy -0.4 random -0.0 realistic +0.0 rival_mid -0.0 station_heavy -0.2 std_tag +0.0 strong_mixed -0.0 zoo_default -0.2, d_classifier_L2: broken_heavy -0.8 event_like -0.0 event_like_prep -0.0 github_heavy +0.6 github_tough -3.6 jammer_heavy -0.7 llm_heavy +0.0 maniac_heavy -1.4 nit_heavy +0.2 prepped_heavy -0.7 random -0.5 realistic -0.5 rival_mid -0.6 station_heavy +0.5 std_tag -1.2 strong_mixed -0.6 zoo_default -0.4, g_bayes_L1+L2: broken_heavy +0.0 event_like +0.0 event_like_prep +0.0 github_heavy +0.1 github_tough -4.3 jammer_heavy -0.6 llm_heavy +0.0 maniac_heavy -1.0 nit_heavy +0.5 prepped_heavy -0.4 random -0.2 realistic -0.0 rival_mid -0.1 station_heavy +1.8 std_tag -0.6 strong_mixed -0.0 zoo_default -0.0, f_oracle: broken_heavy +0.0 event_like +0.8 event_like_prep +0.9 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.0 llm_heavy +0.3 maniac_heavy +2.4 nit_heavy +1.1 prepped_heavy +1.2 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.3 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### no sim-to-real bias (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.8730 | 1.3713 | +0.00 ±0.00 | +0.00 | +0.00 | 0.52 |
| b_fixed_ev_t4 | 1.7262 | 1.2741 | -14.69 ±0.09 | -21.82 | -24.89 | 15.21 |
| c_handoff_rule | 1.8720 | 1.3652 | -0.10 ±0.01 | +0.00 | -9.48 | 0.62 |
| c2_bayes_L1 | 1.8725 | 1.3685 | -0.05 ±0.01 | -0.53 | -3.79 | 0.57 |
| d_classifier_L2 | 1.8677 | 1.3705 | -0.53 ±0.03 | -3.42 | -10.38 | 1.05 |
| d3_classifier_L2_m3 | 1.8711 | 1.3705 | -0.20 ±0.02 | -1.70 | -10.15 | 0.72 |
| d2_centroid_L2 | 1.8621 | 1.3695 | -1.09 ±0.03 | -4.28 | -6.33 | 1.62 |
| e_explore_L1 | 1.8714 | 1.3689 | -0.16 ±0.01 | -0.54 | -2.91 | 0.69 |
| g_bayes_L1+L2 | 1.8707 | 1.3678 | -0.24 ±0.02 | -2.21 | -5.81 | 0.76 |
| h_station_rule_L2 | 1.8744 | 1.3713 | +0.14 ±0.02 | +0.00 | -0.28 | 0.39 |
| f_oracle | 1.8783 | 1.3752 | +0.52 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -0.8 event_like +0.0 event_like_prep +0.0 github_heavy +0.6 github_tough -0.7 jammer_heavy +0.0 llm_heavy +0.0 maniac_heavy +0.0 nit_heavy +0.0 prepped_heavy -0.3 random -0.0 realistic +0.0 rival_mid +0.0 station_heavy -0.3 std_tag +0.0 strong_mixed +0.0 zoo_default -0.2, d_classifier_L2: broken_heavy -0.8 event_like -0.0 event_like_prep -0.0 github_heavy +0.6 github_tough -3.5 jammer_heavy -0.7 llm_heavy +0.0 maniac_heavy -1.4 nit_heavy +0.2 prepped_heavy -0.6 random -0.5 realistic -0.5 rival_mid -0.5 station_heavy +0.6 std_tag -1.2 strong_mixed -0.6 zoo_default -0.4, g_bayes_L1+L2: broken_heavy +0.0 event_like +0.0 event_like_prep +0.0 github_heavy +0.1 github_tough -4.1 jammer_heavy -0.6 llm_heavy +0.0 maniac_heavy -1.0 nit_heavy +0.5 prepped_heavy -0.4 random -0.2 realistic -0.0 rival_mid -0.1 station_heavy +1.8 std_tag -0.5 strong_mixed +0.0 zoo_default -0.0, f_oracle: broken_heavy +0.0 event_like +0.8 event_like_prep +0.9 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.0 llm_heavy +0.3 maniac_heavy +2.4 nit_heavy +1.1 prepped_heavy +1.2 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.3 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### bias sd 10% (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.8730 | 1.3713 | +0.00 ±0.00 | +0.00 | +0.00 | 0.52 |
| b_fixed_ev_t4 | 1.7262 | 1.2741 | -14.69 ±0.09 | -21.82 | -24.89 | 15.21 |
| c_handoff_rule | 1.8715 | 1.3561 | -0.15 ±0.02 | +0.00 | -16.33 | 0.68 |
| c2_bayes_L1 | 1.8722 | 1.3685 | -0.08 ±0.01 | -0.56 | -8.02 | 0.60 |
| d_classifier_L2 | 1.8677 | 1.3705 | -0.53 ±0.03 | -3.42 | -10.38 | 1.05 |
| d3_classifier_L2_m3 | 1.8711 | 1.3705 | -0.20 ±0.02 | -1.70 | -10.15 | 0.72 |
| d2_centroid_L2 | 1.8621 | 1.3695 | -1.09 ±0.03 | -4.28 | -6.33 | 1.62 |
| e_explore_L1 | 1.8711 | 1.3695 | -0.19 ±0.01 | -0.77 | -8.05 | 0.71 |
| g_bayes_L1+L2 | 1.8707 | 1.3685 | -0.24 ±0.02 | -2.26 | -5.81 | 0.76 |
| h_station_rule_L2 | 1.8744 | 1.3713 | +0.14 ±0.02 | +0.00 | -0.28 | 0.39 |
| f_oracle | 1.8783 | 1.3752 | +0.52 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -0.9 event_like -0.1 event_like_prep +0.0 github_heavy +0.3 github_tough -0.9 jammer_heavy -0.0 llm_heavy +0.0 maniac_heavy +0.1 nit_heavy +0.0 prepped_heavy -0.3 random -0.0 realistic +0.0 rival_mid -0.2 station_heavy +0.1 std_tag +0.0 strong_mixed -0.2 zoo_default -0.2, d_classifier_L2: broken_heavy -0.8 event_like -0.0 event_like_prep -0.0 github_heavy +0.6 github_tough -3.5 jammer_heavy -0.7 llm_heavy +0.0 maniac_heavy -1.4 nit_heavy +0.2 prepped_heavy -0.6 random -0.5 realistic -0.5 rival_mid -0.5 station_heavy +0.6 std_tag -1.2 strong_mixed -0.6 zoo_default -0.4, g_bayes_L1+L2: broken_heavy +0.0 event_like -0.0 event_like_prep +0.0 github_heavy +0.1 github_tough -3.9 jammer_heavy -0.6 llm_heavy +0.0 maniac_heavy -1.0 nit_heavy +0.4 prepped_heavy -0.4 random -0.2 realistic -0.0 rival_mid -0.0 station_heavy +1.7 std_tag -0.4 strong_mixed -0.2 zoo_default -0.0, f_oracle: broken_heavy +0.0 event_like +0.8 event_like_prep +0.9 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.0 llm_heavy +0.3 maniac_heavy +2.4 nit_heavy +1.1 prepped_heavy +1.2 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.3 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### heavy drift 20%/step (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.8264 | 1.3577 | +0.00 ±0.00 | +0.00 | +0.00 | 0.37 |
| b_fixed_ev_t4 | 1.6799 | 1.2630 | -14.65 ±0.09 | -22.00 | -24.89 | 15.02 |
| c_handoff_rule | 1.8249 | 1.3420 | -0.15 ±0.02 | +0.00 | -16.06 | 0.51 |
| c2_bayes_L1 | 1.8254 | 1.3557 | -0.10 ±0.01 | -0.54 | -10.68 | 0.47 |
| d_classifier_L2 | 1.8204 | 1.3474 | -0.60 ±0.03 | -3.58 | -8.10 | 0.97 |
| d3_classifier_L2_m3 | 1.8242 | 1.3532 | -0.22 ±0.02 | -1.64 | -8.10 | 0.59 |
| d2_centroid_L2 | 1.8173 | 1.3534 | -0.91 ±0.03 | -3.33 | -6.51 | 1.28 |
| e_explore_L1 | 1.8236 | 1.3532 | -0.28 ±0.01 | -1.06 | -11.06 | 0.65 |
| g_bayes_L1+L2 | 1.8239 | 1.3546 | -0.25 ±0.02 | -1.64 | -9.35 | 0.62 |
| h_station_rule_L2 | 1.8270 | 1.3577 | +0.06 ±0.01 | +0.00 | -0.28 | 0.31 |
| f_oracle | 1.8301 | 1.3580 | +0.37 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -0.6 event_like -0.0 event_like_prep -0.0 github_heavy +0.2 github_tough -0.6 jammer_heavy +0.0 llm_heavy +0.0 maniac_heavy +0.0 nit_heavy +0.0 prepped_heavy -1.8 random -0.0 realistic +0.0 rival_mid -0.0 station_heavy -0.1 std_tag +0.0 strong_mixed -0.1 zoo_default -0.2, d_classifier_L2: broken_heavy -0.7 event_like -0.1 event_like_prep -0.1 github_heavy -0.1 github_tough -2.9 jammer_heavy -0.9 llm_heavy -0.1 maniac_heavy -1.3 nit_heavy -0.1 prepped_heavy -0.6 random -0.5 realistic -0.6 rival_mid -0.6 station_heavy -0.0 std_tag -1.1 strong_mixed -0.7 zoo_default -0.6, g_bayes_L1+L2: broken_heavy -0.0 event_like -0.1 event_like_prep -0.1 github_heavy +0.0 github_tough -2.4 jammer_heavy -0.3 llm_heavy -0.0 maniac_heavy -0.5 nit_heavy +0.4 prepped_heavy -1.3 random -0.2 realistic -0.1 rival_mid -0.2 station_heavy +0.8 std_tag -0.4 strong_mixed -0.4 zoo_default -0.1, f_oracle: broken_heavy +0.0 event_like +0.6 event_like_prep +0.7 github_heavy +0.6 github_tough +0.0 jammer_heavy +0.1 llm_heavy +0.3 maniac_heavy +1.4 nit_heavy +0.8 prepped_heavy +0.8 random +0.2 realistic +0.0 rival_mid +0.1 station_heavy +2.5 std_tag +0.1 strong_mixed +0.0 zoo_default +0.2

### Per named scenario (main config, 300 events each): gain vs fixed cand, % of fair

| scenario | a_fixed_cand | b_fixed_ev_t4 | c_handoff_rule | c2_bayes_L1 | d_classifier_L2 | d3_classifier_L2_m3 | d2_centroid_L2 | e_explore_L1 | g_bayes_L1+L2 | h_station_rule_L2 | f_oracle |
|---|---|---|---|---|---|---|---|---|---|---|---|
| std_tag | +0.0 | -19.5 | +0.0 | +0.0 | -1.2 | -0.7 | -0.6 | -0.4 | -0.5 | +0.0 | +0.0 |
| llm_heavy | +0.0 | -19.3 | +0.0 | +0.0 | -0.0 | -0.0 | -0.1 | -0.0 | -0.0 | +0.0 | +0.3 |
| jammer_heavy | +0.0 | -15.6 | +0.0 | +0.0 | -0.7 | -0.3 | -0.5 | -0.2 | -0.5 | +0.0 | +0.1 |
| station_heavy | +0.0 | -9.0 | +0.0 | -0.3 | +1.5 | +0.8 | +5.2 | -0.3 | +3.0 | +5.6 | +5.9 |
| nit_heavy | +0.0 | -22.1 | +0.0 | +0.0 | +0.3 | +0.1 | -0.2 | +0.2 | +0.6 | +0.0 | +1.2 |
| maniac_heavy | +0.0 | -6.5 | +0.0 | +0.0 | -0.9 | -0.7 | -1.9 | +0.1 | -1.0 | +0.0 | +2.6 |
| prepped_heavy | +0.0 | -2.9 | -2.9 | -0.3 | -0.6 | -0.3 | -0.0 | -0.3 | -0.3 | +0.0 | +1.2 |
| broken_heavy | +0.0 | -20.2 | +0.0 | -0.7 | -1.3 | -0.4 | -0.3 | -0.8 | +0.0 | +0.0 | +0.0 |
| realistic | +0.0 | -16.4 | +0.0 | +0.0 | -0.5 | -0.1 | -0.4 | -0.2 | -0.0 | +0.0 | +0.0 |
| zoo_default | +0.0 | -16.6 | +0.0 | -0.1 | -0.3 | -0.0 | -1.5 | -0.2 | -0.0 | +0.0 | +0.2 |
| rival_mid | +0.0 | -22.6 | +0.0 | -0.0 | -0.5 | -0.2 | -0.6 | -0.3 | -0.1 | +0.0 | +0.0 |
| strong_mixed | +0.0 | -13.2 | +0.0 | -0.0 | -0.6 | -0.1 | -0.2 | -0.3 | -0.0 | +0.0 | +0.0 |
| github_heavy | +0.0 | -16.9 | +0.0 | +0.7 | +0.6 | +0.2 | -4.1 | +0.8 | +0.1 | -0.0 | +1.2 |
| github_tough | +0.0 | -10.7 | +0.0 | -0.7 | -3.7 | -1.3 | -5.0 | -0.8 | -4.2 | -0.0 | +0.0 |
| event_like | +0.0 | -13.1 | +0.0 | -0.0 | -0.0 | +0.0 | -0.0 | -0.0 | +0.0 | +0.0 | +1.0 |
| event_like_prep | +0.0 | -11.8 | +0.0 | +0.0 | -0.0 | +0.0 | -0.0 | +0.0 | +0.0 | +0.0 | +1.1 |
