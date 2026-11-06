# Real-SNG validation (300 paired SNGs per tournament, fresh seeds)

Each round plays real SNGs for every strategy some policy picked, plus cand, paired. Gain of each policy vs fixed cand in weighted x-fair, % of fair: real SNGs / payoff model on the same drifting fields (f_oracle picks by the model here).

| scenario | event | drift | a_fixed_cand | b_fixed_ev_t4 | c_handoff_rule | c2_bayes_L1 | d_classifier_L2 | d3_classifier_L2_m3 | d2_centroid_L2 | e_explore_L1 | g_bayes_L1+L2 | f_oracle |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| station_heavy | 0 | prep | +0.0 / +0.0 | -11.1 / -7.2 | +0.0 / +0.0 | -1.4 / -1.8 | +0.3 / -1.8 | +0.0 / +0.0 | -2.1 / +2.6 | -1.8 / -1.1 | -1.4 / -1.8 | +0.1 / +4.6 |
| station_heavy | 1 | random | +0.0 / +0.0 | -14.1 / -13.2 | +0.0 / +0.0 | -1.2 / +1.4 | -0.7 / +1.7 | -1.0 / +1.7 | +0.4 / +4.1 | -0.9 / +0.9 | -0.7 / +1.7 | -0.2 / +4.1 |
| nit_heavy | 2 | fix | +0.0 / +0.0 | -20.0 / -24.0 | +0.0 / +0.0 | -1.6 / -0.6 | +0.0 / +0.0 | +0.0 / +0.0 | +3.3 / -1.0 | +0.3 / -0.2 | -0.1 / -0.0 | +0.2 / +0.1 |
| nit_heavy | 3 | fix | +0.0 / +0.0 | -18.5 / -24.0 | +0.0 / +0.0 | +1.3 / -0.8 | +0.0 / +0.0 | +0.0 / +0.0 | +4.6 / -0.9 | +0.9 / -0.2 | +0.2 / +0.1 | +0.5 / +0.2 |
| realistic | 4 | pushfold | +0.0 / +0.0 | -13.5 / -16.0 | +0.0 / +0.0 | -0.4 / -0.1 | -0.5 / -0.9 | +0.0 / +0.0 | +0.3 / -0.8 | -0.5 / -0.1 | +0.0 / +0.0 | +0.0 / +0.0 |
| realistic | 5 | fix | +0.0 / +0.0 | -15.5 / -19.5 | +0.0 / +0.0 | -0.5 / -0.1 | +0.0 / +0.0 | +0.0 / +0.0 | +0.0 / +0.0 | -0.4 / -0.2 | +0.0 / +0.0 | +0.0 / +0.0 |

Picks per policy (T1..T6):

- station_heavy #0: a_fixed_cand: cand,cand,cand,cand,cand,cand; b_fixed_ev_t4: ev_t4,ev_t4,ev_t4,ev_t4,ev_t4,ev_t4; c_handoff_rule: cand,cand,cand,cand,cand,cand; c2_bayes_L1: c_value,c_value,c_value,c_value,c_value,c_value; d_classifier_L2: c_value,r2p0,r2p0,r2p0,r2p0,r2p0; d3_classifier_L2_m3: cand,cand,cand,cand,cand,cand; d2_centroid_L2: r2p0,r2p0,r2p0,c_steal,c_steal,c_steal; e_explore_L1: cand,c_value,c_value,c_value,c_value,cand; g_bayes_L1+L2: c_value,c_value,c_value,c_value,c_value,c_value; f_oracle: r2p0,r2p0,r2p0,r2p0,r2p0,r2p0
- station_heavy #1: a_fixed_cand: cand,cand,cand,cand,cand,cand; b_fixed_ev_t4: ev_t4,ev_t4,ev_t4,ev_t4,ev_t4,ev_t4; c_handoff_rule: cand,cand,cand,cand,cand,cand; c2_bayes_L1: c_value,c_value,c_value,c_value,c_value,c_value; d_classifier_L2: r2p0,c_value,c_value,c_value,c_value,c_value; d3_classifier_L2_m3: r2p0,cand,c_value,c_value,c_value,c_value; d2_centroid_L2: r2p0,r2p0,r2p0,r2p0,r2p0,c_steal; e_explore_L1: cand,c_value,c_value,c_value,c_value,c_value; g_bayes_L1+L2: r2p0,c_value,c_value,c_value,c_value,c_value; f_oracle: r2p0,r2p0,r2p0,r2p0,r2p0,r2p0
- nit_heavy #2: a_fixed_cand: cand,cand,cand,cand,cand,cand; b_fixed_ev_t4: ev_t4,ev_t4,ev_t4,ev_t4,ev_t4,ev_t4; c_handoff_rule: cand,cand,cand,cand,cand,cand; c2_bayes_L1: c_value,c_value,c_value,c_value,c_value,cand; d_classifier_L2: cand,cand,cand,cand,cand,cand; d3_classifier_L2_m3: cand,cand,cand,cand,cand,cand; d2_centroid_L2: c_steal,c_steal,c_steal,c_steal,c_steal,cand; e_explore_L1: cand,c_value,cand,cand,cand,cand; g_bayes_L1+L2: c_value,cand,cand,cand,cand,cand; f_oracle: c_value,c_value,cand,cand,cand,cand
- nit_heavy #3: a_fixed_cand: cand,cand,cand,cand,cand,cand; b_fixed_ev_t4: ev_t4,ev_t4,ev_t4,ev_t4,ev_t4,ev_t4; c_handoff_rule: cand,cand,cand,cand,cand,cand; c2_bayes_L1: c_value,c_value,c_value,c_value,c_value,cand; d_classifier_L2: cand,cand,cand,cand,cand,cand; d3_classifier_L2_m3: cand,cand,cand,cand,cand,cand; d2_centroid_L2: c_steal,c_steal,c_steal,c_steal,c_steal,cand; e_explore_L1: cand,c_value,c_value,cand,c_value,cand; g_bayes_L1+L2: cand,c_value,c_value,cand,cand,cand; f_oracle: c_value,c_value,c_value,cand,cand,cand
- realistic #4: a_fixed_cand: cand,cand,cand,cand,cand,cand; b_fixed_ev_t4: ev_t4,ev_t4,ev_t4,ev_t4,ev_t4,ev_t4; c_handoff_rule: cand,cand,cand,cand,cand,cand; c2_bayes_L1: c_value,cand,cand,cand,cand,cand; d_classifier_L2: cand,cand,cand,cand,c_steal,cand; d3_classifier_L2_m3: cand,cand,cand,cand,cand,cand; d2_centroid_L2: c_steal,cand,cand,cand,cand,cand; e_explore_L1: cand,c_value,cand,cand,cand,cand; g_bayes_L1+L2: cand,cand,cand,cand,cand,cand; f_oracle: cand,cand,cand,cand,cand,cand
- realistic #5: a_fixed_cand: cand,cand,cand,cand,cand,cand; b_fixed_ev_t4: ev_t4,ev_t4,ev_t4,ev_t4,ev_t4,ev_t4; c_handoff_rule: cand,cand,cand,cand,cand,cand; c2_bayes_L1: c_value,cand,cand,cand,cand,cand; d_classifier_L2: cand,cand,cand,cand,cand,cand; d3_classifier_L2_m3: cand,cand,cand,cand,cand,cand; d2_centroid_L2: cand,cand,cand,cand,cand,cand; e_explore_L1: cand,c_value,cand,cand,cand,cand; g_bayes_L1+L2: cand,cand,cand,cand,cand,cand; f_oracle: cand,cand,cand,cand,cand,cand

Real x-fair of the strategies played, per round (model in brackets):

- station_heavy #0 T1: cand 2.127 (2.155), ev_t4 2.057 (2.081), r2p0 2.118 (2.221), c_value 2.168 (2.144)
- station_heavy #0 T2: cand 2.126 (2.116), ev_t4 1.996 (2.043), r2p0 2.161 (2.178), c_value 2.172 (2.103)
- station_heavy #0 T3: cand 2.101 (2.029), ev_t4 1.960 (1.956), r2p0 2.014 (2.078), c_value 2.079 (2.012)
- station_heavy #0 T4: cand 1.938 (2.012), ev_t4 1.934 (1.940), r2p0 2.020 (2.060), c_value 1.946 (1.995), c_steal 2.025 (1.980)
- station_heavy #0 T5: cand 1.937 (1.967), ev_t4 1.746 (1.895), r2p0 1.936 (2.008), c_value 1.849 (1.947), c_steal 1.907 (1.934)
- station_heavy #0 T6: cand 1.938 (1.937), ev_t4 1.836 (1.866), r2p0 1.918 (1.975), c_value 1.946 (1.916), c_steal 1.863 (1.904)
- station_heavy #1 T1: cand 2.304 (2.271), ev_t4 2.265 (2.174), r2p0 2.345 (2.340), c_value 2.239 (2.274)
- station_heavy #1 T2: cand 2.209 (2.246), ev_t4 2.119 (2.134), r2p0 2.276 (2.303), c_value 2.237 (2.253)
- station_heavy #1 T3: cand 2.268 (2.228), ev_t4 2.117 (2.106), r2p0 2.362 (2.277), c_value 2.258 (2.240)
- station_heavy #1 T4: cand 2.192 (2.210), ev_t4 2.070 (2.078), r2p0 2.147 (2.251), c_value 2.143 (2.225)
- station_heavy #1 T5: cand 2.200 (2.203), ev_t4 2.080 (2.067), r2p0 2.179 (2.240), c_value 2.232 (2.219)
- station_heavy #1 T6: cand 2.228 (2.192), ev_t4 2.031 (2.048), r2p0 2.194 (2.224), c_value 2.199 (2.210), c_steal 2.214 (2.178)
- nit_heavy #2 T1: cand 2.059 (1.977), ev_t4 1.795 (1.735), c_value 2.037 (1.986), c_steal 2.102 (1.974)
- nit_heavy #2 T2: cand 1.908 (1.960), ev_t4 1.732 (1.719), c_value 1.936 (1.964), c_steal 1.983 (1.956)
- nit_heavy #2 T3: cand 1.930 (1.932), ev_t4 1.723 (1.691), c_value 1.887 (1.926), c_steal 2.056 (1.924)
- nit_heavy #2 T4: cand 1.924 (1.920), ev_t4 1.768 (1.679), c_value 1.967 (1.910), c_steal 1.944 (1.910)
- nit_heavy #2 T5: cand 1.938 (1.901), ev_t4 1.667 (1.662), c_value 1.856 (1.885), c_steal 1.946 (1.890)
- nit_heavy #2 T6: cand 1.818 (1.890), ev_t4 1.651 (1.651)
- nit_heavy #3 T1: cand 1.952 (1.991), ev_t4 1.754 (1.749), c_value 1.998 (2.005), c_steal 1.995 (1.991)
- nit_heavy #3 T2: cand 1.968 (1.983), ev_t4 1.746 (1.741), c_value 2.015 (1.994), c_steal 2.064 (1.981)
- nit_heavy #3 T3: cand 1.890 (1.955), ev_t4 1.629 (1.714), c_value 1.876 (1.956), c_steal 1.969 (1.950)
- nit_heavy #3 T4: cand 1.902 (1.924), ev_t4 1.784 (1.684), c_value 1.912 (1.916), c_steal 2.001 (1.916)
- nit_heavy #3 T5: cand 1.892 (1.903), ev_t4 1.685 (1.663), c_value 1.918 (1.887), c_steal 1.912 (1.891)
- nit_heavy #3 T6: cand 1.769 (1.897), ev_t4 1.612 (1.658)
- realistic #4 T1: cand 1.746 (1.739), ev_t4 1.517 (1.573), c_value 1.662 (1.725), c_steal 1.811 (1.713)
- realistic #4 T2: cand 1.751 (1.764), ev_t4 1.509 (1.599), c_value 1.697 (1.750)
- realistic #4 T3: cand 1.780 (1.793), ev_t4 1.631 (1.630)
- realistic #4 T4: cand 1.861 (1.830), ev_t4 1.812 (1.670)
- realistic #4 T5: cand 1.867 (1.845), ev_t4 1.701 (1.687), c_steal 1.846 (1.832)
- realistic #4 T6: cand 1.890 (1.862), ev_t4 1.781 (1.705)
- realistic #5 T1: cand 1.689 (1.697), ev_t4 1.449 (1.523), c_value 1.578 (1.678)
- realistic #5 T2: cand 1.680 (1.704), ev_t4 1.509 (1.523), c_value 1.638 (1.680)
- realistic #5 T3: cand 1.747 (1.711), ev_t4 1.544 (1.522)
- realistic #5 T4: cand 1.752 (1.715), ev_t4 1.546 (1.521)
- realistic #5 T5: cand 1.712 (1.720), ev_t4 1.539 (1.521)
- realistic #5 T6: cand 1.624 (1.723), ev_t4 1.561 (1.520)
