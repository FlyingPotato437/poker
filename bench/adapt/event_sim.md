# Event simulation

Truth model from 9800 SNGs, knowledge model from 9800 (disjoint halves). 10k-SNG score noise sd = 1.02% of fair. Scores are weighted x-fair (weights 1..6)/21.

Model check (additive model vs each scenario's direct mean, half A): max |level error|, max |error of gain vs cand|, argmax direct / model:

| scenario | level err | gain err | best direct | best model |
|---|---|---|---|---|
| std_tag | 2.9% | 1.5% | cand | cand |
| llm_heavy | 3.0% | 1.9% | c_value | c_value |
| jammer_heavy | 2.3% | 0.9% | cand | cand |
| station_heavy | 1.3% | 1.8% | r2p0 | r2p0 |
| nit_heavy | 1.1% | 1.0% | c_value | c_value |
| maniac_heavy | 1.5% | 0.3% | r2p0 | r2p0 |
| prepped_heavy | 1.6% | 1.9% | x | x |
| broken_heavy | 1.7% | 1.4% | cand | cand |
| realistic | 6.3% | 4.8% | cand | cand |
| strong_mixed | 4.0% | 7.1% | r2p0 | cand |
| github_heavy | 3.7% | 4.0% | c_value | c_value |
| github_tough | 3.5% | 3.3% | cand | cand |
| uniform | 12.5% | 8.7% | c_steal | cand |

Truth-model x-fair per named scenario (all records; this is the matrix the event sim plays on):

| scenario | cand | ev_t4 | x | xex2 | s5p0 | r2p0 | c_calldown | c_value | c_steal | best | best − cand |
|---|---|---|---|---|---|---|---|---|---|---|---|
| std_tag | 1.604 | 1.430 | 1.479 | 1.514 | 1.515 | 1.576 | 1.582 | 1.567 | 1.619 | c_steal | +1.4% |
| llm_heavy | 2.096 | 1.899 | 1.995 | 1.991 | 1.988 | 2.044 | 2.012 | 2.092 | 2.079 | cand | +0.0% |
| jammer_heavy | 2.053 | 1.908 | 1.972 | 1.971 | 1.961 | 2.001 | 2.018 | 2.053 | 2.067 | c_steal | +1.5% |
| station_heavy | 2.326 | 2.215 | 2.343 | 2.314 | 2.303 | 2.395 | 2.165 | 2.338 | 2.317 | r2p0 | +6.9% |
| nit_heavy | 2.007 | 1.769 | 1.919 | 1.918 | 1.871 | 1.963 | 1.924 | 2.042 | 2.031 | c_value | +3.5% |
| maniac_heavy | 2.090 | 2.028 | 2.074 | 2.094 | 2.085 | 2.118 | 2.044 | 2.093 | 2.087 | r2p0 | +2.7% |
| prepped_heavy | 1.059 | 1.044 | 1.055 | 1.034 | 1.042 | 1.006 | 1.031 | 1.039 | 0.963 | cand | +0.0% |
| broken_heavy | 2.302 | 2.088 | 2.217 | 2.257 | 2.192 | 2.256 | 2.231 | 2.261 | 2.280 | cand | +0.0% |
| realistic | 1.669 | 1.509 | 1.565 | 1.603 | 1.584 | 1.621 | 1.629 | 1.650 | 1.639 | cand | +0.0% |
| zoo_default | 2.315 | 2.150 | 2.242 | 2.260 | 2.245 | 2.295 | 2.256 | 2.308 | 2.313 | cand | +0.0% |
| rival_mid | 1.984 | 1.770 | 1.862 | 1.934 | 1.852 | 1.874 | 1.875 | 1.974 | 2.016 | c_steal | +3.2% |
| strong_mixed | 1.430 | 1.320 | 1.337 | 1.392 | 1.363 | 1.391 | 1.399 | 1.399 | 1.380 | cand | +0.0% |
| github_heavy | 2.242 | 2.082 | 2.204 | 2.180 | 2.197 | 2.225 | 2.230 | 2.261 | 2.229 | c_value | +1.9% |
| github_tough | 2.295 | 2.207 | 2.245 | 2.245 | 2.216 | 2.285 | 2.272 | 2.283 | 2.293 | cand | +0.0% |

### main: practice 1000 hands, bias sd 5%, drift 8%/step (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.9201 | 1.4048 | +0.00 ±0.00 | +0.00 | +0.00 | 0.59 |
| b_fixed_ev_t4 | 1.7696 | 1.3005 | -15.05 ±0.09 | -22.05 | -24.93 | 15.64 |
| c_handoff_rule | 1.9187 | 1.3942 | -0.14 ±0.02 | +0.00 | -10.61 | 0.73 |
| c2_bayes_L1 | 1.9108 | 1.4047 | -0.92 ±0.03 | -4.68 | -6.04 | 1.52 |
| d_classifier_L2 | 1.9144 | 1.3990 | -0.57 ±0.03 | -3.59 | -11.00 | 1.16 |
| d3_classifier_L2_m3 | 1.9193 | 1.4045 | -0.08 ±0.02 | -1.06 | -8.45 | 0.67 |
| d2_centroid_L2 | 1.9116 | 1.4045 | -0.85 ±0.03 | -3.63 | -5.94 | 1.45 |
| e_explore_L1 | 1.9175 | 1.4046 | -0.26 ±0.01 | -1.49 | -3.81 | 0.85 |
| g_bayes_L1+L2 | 1.9149 | 1.4045 | -0.52 ±0.03 | -3.35 | -5.97 | 1.12 |
| h_station_rule_L2 | 1.9224 | 1.4048 | +0.23 ±0.02 | +0.00 | -0.28 | 0.36 |
| f_oracle | 1.9260 | 1.4053 | +0.59 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -5.2 github_heavy +0.8 github_tough -5.1 jammer_heavy -1.4 llm_heavy -0.2 maniac_heavy +0.2 nit_heavy +1.0 prepped_heavy -0.0 random -0.8 realistic -0.1 rival_mid -2.5 station_heavy -1.1 std_tag -0.2 strong_mixed -0.1 zoo_default -0.8, d_classifier_L2: broken_heavy -0.1 github_heavy +0.8 github_tough -5.1 jammer_heavy -0.7 llm_heavy -0.0 maniac_heavy -0.5 nit_heavy +0.6 prepped_heavy -0.2 random -0.7 realistic -0.4 rival_mid -0.1 station_heavy +0.8 std_tag -0.9 strong_mixed -0.4 zoo_default -0.3, g_bayes_L1+L2: broken_heavy +0.0 github_heavy +0.3 github_tough -5.0 jammer_heavy -0.7 llm_heavy -0.0 maniac_heavy -1.1 nit_heavy +0.8 prepped_heavy +0.0 random -0.7 realistic -0.0 rival_mid -0.8 station_heavy +1.9 std_tag -0.5 strong_mixed -0.1 zoo_default -0.7, f_oracle: broken_heavy +0.0 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.1 llm_heavy +0.2 maniac_heavy +2.4 nit_heavy +1.2 prepped_heavy +1.0 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.7 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### no practice, bias sd 5% (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.9201 | 1.4048 | +0.00 ±0.00 | +0.00 | +0.00 | 0.59 |
| b_fixed_ev_t4 | 1.7696 | 1.3005 | -15.05 ±0.09 | -22.05 | -24.93 | 15.64 |
| c_handoff_rule | 1.9187 | 1.3942 | -0.14 ±0.02 | +0.00 | -10.61 | 0.73 |
| c2_bayes_L1 | 1.9108 | 1.4047 | -0.92 ±0.03 | -4.68 | -6.04 | 1.52 |
| d_classifier_L2 | 1.9145 | 1.3990 | -0.56 ±0.03 | -3.44 | -10.73 | 1.16 |
| d3_classifier_L2_m3 | 1.9192 | 1.4045 | -0.09 ±0.02 | -1.06 | -8.45 | 0.68 |
| d2_centroid_L2 | 1.9119 | 1.4045 | -0.82 ±0.03 | -3.47 | -5.66 | 1.42 |
| e_explore_L1 | 1.9175 | 1.4046 | -0.26 ±0.01 | -1.49 | -3.81 | 0.85 |
| g_bayes_L1+L2 | 1.9141 | 1.4044 | -0.59 ±0.03 | -3.48 | -5.97 | 1.19 |
| h_station_rule_L2 | 1.9223 | 1.4048 | +0.22 ±0.02 | +0.00 | +0.00 | 0.38 |
| f_oracle | 1.9260 | 1.4053 | +0.59 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -5.2 github_heavy +0.8 github_tough -5.1 jammer_heavy -1.4 llm_heavy -0.2 maniac_heavy +0.2 nit_heavy +1.0 prepped_heavy -0.0 random -0.8 realistic -0.1 rival_mid -2.5 station_heavy -1.1 std_tag -0.2 strong_mixed -0.1 zoo_default -0.8, d_classifier_L2: broken_heavy -0.1 github_heavy +0.7 github_tough -4.9 jammer_heavy -0.7 llm_heavy -0.0 maniac_heavy -0.5 nit_heavy +0.6 prepped_heavy -0.2 random -0.7 realistic -0.4 rival_mid -0.1 station_heavy +0.5 std_tag -0.9 strong_mixed -0.4 zoo_default -0.3, g_bayes_L1+L2: broken_heavy -0.3 github_heavy +0.3 github_tough -5.1 jammer_heavy -0.8 llm_heavy +0.0 maniac_heavy -0.9 nit_heavy +0.9 prepped_heavy -0.0 random -0.7 realistic -0.1 rival_mid -0.9 station_heavy +1.6 std_tag -0.8 strong_mixed -0.2 zoo_default -0.8, f_oracle: broken_heavy +0.0 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.1 llm_heavy +0.2 maniac_heavy +2.4 nit_heavy +1.2 prepped_heavy +1.0 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.7 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### practice 200 hands (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.9201 | 1.4048 | +0.00 ±0.00 | +0.00 | +0.00 | 0.59 |
| b_fixed_ev_t4 | 1.7696 | 1.3005 | -15.05 ±0.09 | -22.05 | -24.93 | 15.64 |
| c_handoff_rule | 1.9187 | 1.3942 | -0.14 ±0.02 | +0.00 | -10.61 | 0.73 |
| c2_bayes_L1 | 1.9108 | 1.4047 | -0.92 ±0.03 | -4.68 | -6.04 | 1.52 |
| d_classifier_L2 | 1.9143 | 1.3974 | -0.58 ±0.03 | -3.57 | -11.00 | 1.17 |
| d3_classifier_L2_m3 | 1.9192 | 1.4045 | -0.09 ±0.02 | -1.07 | -8.45 | 0.68 |
| d2_centroid_L2 | 1.9115 | 1.4044 | -0.86 ±0.03 | -3.58 | -5.94 | 1.45 |
| e_explore_L1 | 1.9175 | 1.4046 | -0.26 ±0.01 | -1.49 | -3.81 | 0.85 |
| g_bayes_L1+L2 | 1.9149 | 1.4045 | -0.52 ±0.03 | -3.35 | -5.97 | 1.11 |
| h_station_rule_L2 | 1.9224 | 1.4048 | +0.23 ±0.02 | +0.00 | -0.28 | 0.36 |
| f_oracle | 1.9260 | 1.4053 | +0.59 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -5.2 github_heavy +0.8 github_tough -5.1 jammer_heavy -1.4 llm_heavy -0.2 maniac_heavy +0.2 nit_heavy +1.0 prepped_heavy -0.0 random -0.8 realistic -0.1 rival_mid -2.5 station_heavy -1.1 std_tag -0.2 strong_mixed -0.1 zoo_default -0.8, d_classifier_L2: broken_heavy -0.1 github_heavy +0.8 github_tough -5.1 jammer_heavy -0.7 llm_heavy +0.0 maniac_heavy -0.5 nit_heavy +0.6 prepped_heavy -0.2 random -0.7 realistic -0.4 rival_mid -0.2 station_heavy +0.6 std_tag -0.9 strong_mixed -0.4 zoo_default -0.3, g_bayes_L1+L2: broken_heavy -0.0 github_heavy +0.2 github_tough -4.9 jammer_heavy -0.7 llm_heavy +0.0 maniac_heavy -1.1 nit_heavy +0.9 prepped_heavy +0.0 random -0.7 realistic -0.0 rival_mid -0.7 station_heavy +1.7 std_tag -0.5 strong_mixed -0.1 zoo_default -0.7, f_oracle: broken_heavy +0.0 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.1 llm_heavy +0.2 maniac_heavy +2.4 nit_heavy +1.2 prepped_heavy +1.0 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.7 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### practice full log (10k SNGs) (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.9201 | 1.4048 | +0.00 ±0.00 | +0.00 | +0.00 | 0.59 |
| b_fixed_ev_t4 | 1.7696 | 1.3005 | -15.05 ±0.09 | -22.05 | -24.93 | 15.64 |
| c_handoff_rule | 1.9187 | 1.3942 | -0.14 ±0.02 | +0.00 | -10.61 | 0.73 |
| c2_bayes_L1 | 1.9108 | 1.4047 | -0.92 ±0.03 | -4.68 | -6.04 | 1.52 |
| d_classifier_L2 | 1.9143 | 1.3990 | -0.57 ±0.03 | -3.60 | -10.99 | 1.17 |
| d3_classifier_L2_m3 | 1.9192 | 1.4045 | -0.09 ±0.02 | -1.11 | -8.87 | 0.68 |
| d2_centroid_L2 | 1.9116 | 1.4044 | -0.85 ±0.04 | -3.63 | -5.94 | 1.44 |
| e_explore_L1 | 1.9175 | 1.4046 | -0.26 ±0.01 | -1.49 | -3.81 | 0.85 |
| g_bayes_L1+L2 | 1.9147 | 1.4045 | -0.54 ±0.03 | -3.39 | -5.97 | 1.14 |
| h_station_rule_L2 | 1.9224 | 1.4048 | +0.23 ±0.02 | +0.00 | +0.00 | 0.36 |
| f_oracle | 1.9260 | 1.4053 | +0.59 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -5.2 github_heavy +0.8 github_tough -5.1 jammer_heavy -1.4 llm_heavy -0.2 maniac_heavy +0.2 nit_heavy +1.0 prepped_heavy -0.0 random -0.8 realistic -0.1 rival_mid -2.5 station_heavy -1.1 std_tag -0.2 strong_mixed -0.1 zoo_default -0.8, d_classifier_L2: broken_heavy -0.1 github_heavy +0.8 github_tough -5.2 jammer_heavy -0.7 llm_heavy -0.0 maniac_heavy -0.5 nit_heavy +0.6 prepped_heavy -0.2 random -0.7 realistic -0.4 rival_mid -0.1 station_heavy +0.8 std_tag -0.9 strong_mixed -0.4 zoo_default -0.3, g_bayes_L1+L2: broken_heavy +0.0 github_heavy +0.2 github_tough -5.0 jammer_heavy -0.7 llm_heavy -0.0 maniac_heavy -1.1 nit_heavy +0.8 prepped_heavy +0.0 random -0.7 realistic -0.0 rival_mid -0.8 station_heavy +1.9 std_tag -0.7 strong_mixed -0.1 zoo_default -0.8, f_oracle: broken_heavy +0.0 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.1 llm_heavy +0.2 maniac_heavy +2.4 nit_heavy +1.2 prepped_heavy +1.0 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.7 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### no sim-to-real bias (handoff thr 0.25, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.9201 | 1.4048 | +0.00 ±0.00 | +0.00 | +0.00 | 0.59 |
| b_fixed_ev_t4 | 1.7696 | 1.3005 | -15.05 ±0.09 | -22.05 | -24.93 | 15.64 |
| c_handoff_rule | 1.9184 | 1.3880 | -0.17 ±0.02 | +0.00 | -10.61 | 0.76 |
| c2_bayes_L1 | 1.9106 | 1.4047 | -0.94 ±0.03 | -4.66 | -6.04 | 1.54 |
| d_classifier_L2 | 1.9144 | 1.3990 | -0.57 ±0.03 | -3.59 | -11.00 | 1.16 |
| d3_classifier_L2_m3 | 1.9193 | 1.4045 | -0.08 ±0.02 | -1.06 | -8.45 | 0.67 |
| d2_centroid_L2 | 1.9116 | 1.4045 | -0.85 ±0.03 | -3.63 | -5.94 | 1.45 |
| e_explore_L1 | 1.9175 | 1.4015 | -0.26 ±0.01 | -1.47 | -3.81 | 0.85 |
| g_bayes_L1+L2 | 1.9149 | 1.4045 | -0.52 ±0.03 | -3.42 | -5.97 | 1.12 |
| h_station_rule_L2 | 1.9224 | 1.4048 | +0.23 ±0.02 | +0.00 | -0.28 | 0.36 |
| f_oracle | 1.9260 | 1.4053 | +0.59 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -5.2 github_heavy +0.8 github_tough -5.1 jammer_heavy -1.5 llm_heavy -0.3 maniac_heavy +0.2 nit_heavy +1.1 prepped_heavy -0.0 random -0.9 realistic -0.1 rival_mid -2.6 station_heavy -1.1 std_tag -0.2 strong_mixed -0.1 zoo_default -0.8, d_classifier_L2: broken_heavy -0.1 github_heavy +0.8 github_tough -5.1 jammer_heavy -0.7 llm_heavy -0.0 maniac_heavy -0.5 nit_heavy +0.6 prepped_heavy -0.2 random -0.7 realistic -0.4 rival_mid -0.1 station_heavy +0.8 std_tag -0.9 strong_mixed -0.4 zoo_default -0.3, g_bayes_L1+L2: broken_heavy +0.0 github_heavy +0.2 github_tough -5.1 jammer_heavy -0.8 llm_heavy -0.0 maniac_heavy -1.1 nit_heavy +1.0 prepped_heavy +0.0 random -0.7 realistic -0.0 rival_mid -0.7 station_heavy +1.9 std_tag -0.6 strong_mixed -0.1 zoo_default -0.6, f_oracle: broken_heavy +0.0 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.1 llm_heavy +0.2 maniac_heavy +2.4 nit_heavy +1.2 prepped_heavy +1.0 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.7 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### bias sd 10% (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.9201 | 1.4048 | +0.00 ±0.00 | +0.00 | +0.00 | 0.59 |
| b_fixed_ev_t4 | 1.7696 | 1.3005 | -15.05 ±0.09 | -22.05 | -24.93 | 15.64 |
| c_handoff_rule | 1.9187 | 1.3991 | -0.14 ±0.02 | +0.00 | -10.95 | 0.73 |
| c2_bayes_L1 | 1.9111 | 1.4047 | -0.89 ±0.03 | -4.59 | -6.04 | 1.49 |
| d_classifier_L2 | 1.9144 | 1.3990 | -0.57 ±0.03 | -3.59 | -11.00 | 1.16 |
| d3_classifier_L2_m3 | 1.9193 | 1.4045 | -0.08 ±0.02 | -1.06 | -8.45 | 0.67 |
| d2_centroid_L2 | 1.9116 | 1.4045 | -0.85 ±0.03 | -3.63 | -5.94 | 1.45 |
| e_explore_L1 | 1.9174 | 1.4045 | -0.26 ±0.02 | -1.53 | -5.54 | 0.86 |
| g_bayes_L1+L2 | 1.9149 | 1.4045 | -0.52 ±0.03 | -3.40 | -5.97 | 1.11 |
| h_station_rule_L2 | 1.9224 | 1.4048 | +0.23 ±0.02 | +0.00 | -0.28 | 0.36 |
| f_oracle | 1.9260 | 1.4053 | +0.59 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -5.0 github_heavy +0.7 github_tough -5.0 jammer_heavy -1.3 llm_heavy -0.2 maniac_heavy +0.2 nit_heavy +0.9 prepped_heavy -0.0 random -0.8 realistic -0.1 rival_mid -2.3 station_heavy -0.8 std_tag -0.2 strong_mixed -0.1 zoo_default -0.8, d_classifier_L2: broken_heavy -0.1 github_heavy +0.8 github_tough -5.1 jammer_heavy -0.7 llm_heavy -0.0 maniac_heavy -0.5 nit_heavy +0.6 prepped_heavy -0.2 random -0.7 realistic -0.4 rival_mid -0.1 station_heavy +0.8 std_tag -0.9 strong_mixed -0.4 zoo_default -0.3, g_bayes_L1+L2: broken_heavy +0.0 github_heavy +0.4 github_tough -5.1 jammer_heavy -0.7 llm_heavy -0.0 maniac_heavy -1.1 nit_heavy +0.7 prepped_heavy +0.0 random -0.7 realistic -0.0 rival_mid -0.7 station_heavy +1.9 std_tag -0.5 strong_mixed -0.1 zoo_default -0.7, f_oracle: broken_heavy +0.0 github_heavy +1.0 github_tough +0.0 jammer_heavy +0.1 llm_heavy +0.2 maniac_heavy +2.4 nit_heavy +1.2 prepped_heavy +1.0 random +0.3 realistic +0.0 rival_mid +0.0 station_heavy +5.7 std_tag +0.0 strong_mixed +0.0 zoo_default +0.2

### heavy drift 20%/step (handoff thr 0.40, 3000 events)

| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|---|
| a_fixed_cand | 1.8622 | 1.3861 | +0.00 ±0.00 | +0.00 | +0.00 | 0.42 |
| b_fixed_ev_t4 | 1.7122 | 1.2893 | -15.00 ±0.09 | -22.32 | -24.93 | 15.42 |
| c_handoff_rule | 1.8606 | 1.3705 | -0.17 ±0.02 | +0.00 | -16.73 | 0.58 |
| c2_bayes_L1 | 1.8516 | 1.3802 | -1.06 ±0.03 | -4.18 | -6.30 | 1.48 |
| d_classifier_L2 | 1.8559 | 1.3834 | -0.63 ±0.03 | -3.29 | -11.62 | 1.05 |
| d3_classifier_L2_m3 | 1.8615 | 1.3861 | -0.07 ±0.02 | -0.70 | -6.99 | 0.49 |
| d2_centroid_L2 | 1.8541 | 1.3806 | -0.81 ±0.03 | -3.09 | -6.02 | 1.23 |
| e_explore_L1 | 1.8582 | 1.3831 | -0.40 ±0.01 | -1.72 | -3.81 | 0.82 |
| g_bayes_L1+L2 | 1.8572 | 1.3835 | -0.50 ±0.03 | -2.84 | -6.20 | 0.91 |
| h_station_rule_L2 | 1.8635 | 1.3861 | +0.13 ±0.02 | +0.00 | -0.28 | 0.29 |
| f_oracle | 1.8664 | 1.3864 | +0.42 ±0.02 | +0.00 | +0.00 | 0.00 |

Gain vs fixed cand by base field (% of fair): c2_bayes_L1: broken_heavy -4.2 github_heavy -0.4 github_tough -4.3 jammer_heavy -1.3 llm_heavy -0.7 maniac_heavy -0.4 nit_heavy +0.2 prepped_heavy -0.0 random -1.0 realistic -0.1 rival_mid -2.2 station_heavy -1.5 std_tag -0.2 strong_mixed -0.1 zoo_default -1.4, d_classifier_L2: broken_heavy -0.2 github_heavy +0.3 github_tough -3.9 jammer_heavy -0.9 llm_heavy -0.1 maniac_heavy -0.5 nit_heavy +0.3 prepped_heavy -0.3 random -0.7 realistic -0.5 rival_mid -0.3 station_heavy -0.1 std_tag -0.8 strong_mixed -0.7 zoo_default -0.5, g_bayes_L1+L2: broken_heavy -0.2 github_heavy -0.1 github_tough -3.3 jammer_heavy -0.5 llm_heavy -0.1 maniac_heavy -0.5 nit_heavy +0.5 prepped_heavy -0.1 random -0.6 realistic -0.1 rival_mid -0.7 station_heavy +0.8 std_tag -0.5 strong_mixed -0.3 zoo_default -0.6, f_oracle: broken_heavy +0.0 github_heavy +0.6 github_tough +0.0 jammer_heavy +0.2 llm_heavy +0.3 maniac_heavy +1.4 nit_heavy +0.8 prepped_heavy +0.8 random +0.2 realistic +0.0 rival_mid +0.1 station_heavy +3.2 std_tag +0.1 strong_mixed +0.0 zoo_default +0.2

### Per named scenario (main config, 300 events each): gain vs fixed cand, % of fair

| scenario | a_fixed_cand | b_fixed_ev_t4 | c_handoff_rule | c2_bayes_L1 | d_classifier_L2 | d3_classifier_L2_m3 | d2_centroid_L2 | e_explore_L1 | g_bayes_L1+L2 | h_station_rule_L2 | f_oracle |
|---|---|---|---|---|---|---|---|---|---|---|---|
| std_tag | +0.0 | -19.5 | +0.0 | -0.2 | -0.9 | -0.5 | -0.6 | -0.5 | -0.5 | +0.0 | +0.0 |
| llm_heavy | +0.0 | -19.3 | +0.0 | -0.3 | -0.0 | +0.0 | -0.1 | -0.1 | -0.0 | +0.0 | +0.2 |
| jammer_heavy | +0.0 | -15.7 | +0.0 | -1.4 | -0.8 | -0.3 | -0.5 | -0.5 | -0.8 | +0.0 | +0.1 |
| station_heavy | +0.0 | -9.3 | +0.0 | -1.2 | +0.9 | +1.3 | +4.9 | -0.5 | +1.6 | +5.3 | +5.7 |
| nit_heavy | +0.0 | -22.1 | +0.0 | +0.9 | +0.4 | +0.0 | -0.1 | +0.8 | +0.8 | +0.0 | +1.1 |
| maniac_heavy | +0.0 | -6.8 | +0.0 | +0.2 | -0.5 | -0.3 | -2.3 | +0.3 | -1.1 | +0.0 | +2.5 |
| prepped_heavy | +0.0 | -3.5 | -3.5 | -0.0 | -0.3 | -0.0 | -0.1 | -0.2 | +0.0 | +0.0 | +0.9 |
| broken_heavy | +0.0 | -20.2 | +0.0 | -5.2 | -0.1 | -0.0 | -0.3 | -1.2 | +0.0 | +0.0 | +0.0 |
| realistic | +0.0 | -16.5 | +0.0 | -0.1 | -0.3 | -0.0 | -0.4 | -0.2 | -0.0 | +0.0 | +0.0 |
| zoo_default | +0.0 | -16.7 | +0.0 | -0.8 | -0.4 | -0.0 | -1.5 | -0.3 | -0.6 | +0.0 | +0.2 |
| rival_mid | +0.0 | -22.6 | +0.0 | -2.5 | -0.3 | +0.0 | -0.6 | -0.8 | -0.7 | +0.0 | +0.0 |
| strong_mixed | +0.0 | -13.6 | +0.0 | -0.1 | -0.4 | -0.0 | -0.2 | -0.2 | -0.1 | +0.0 | +0.0 |
| github_heavy | +0.0 | -17.0 | +0.0 | +0.8 | +0.8 | +0.1 | +0.7 | +0.8 | +0.2 | +0.0 | +1.1 |
| github_tough | +0.0 | -10.9 | +0.0 | -5.1 | -5.1 | -1.8 | -5.3 | -1.2 | -5.1 | -0.0 | +0.0 |
