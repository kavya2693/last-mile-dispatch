# Run report

26 hubs, 28 experiment days, 326,981 orders. Runtime 179.8 s.

## Ablation (every policy on every hub-day)

| policy | orders | delivered | cost_per_delivered | orders_per_rider_hour | utilization | fake_accepted_per_1k | on_time_share_of_orders | on_time_share_of_delivered | cancel_rate | false_flags_per_1k | km_per_delivered | lead_p90 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 326981.000 | 277885.000 | 9.706 | 2.623 | 0.677 | 15.102 | 0.565 | 0.664 | 0.115 | 0.000 | 4.516 | 41.911 |
| bagging | 326981.000 | 299736.000 | 8.948 | 2.829 | 0.650 | 16.038 | 0.781 | 0.852 | 0.045 | 0.000 | 3.932 | 31.902 |
| matching | 326981.000 | 286727.000 | 9.315 | 2.706 | 0.665 | 15.992 | 0.689 | 0.786 | 0.086 | 0.000 | 4.286 | 35.189 |
| bagging+matching | 326981.000 | 303566.000 | 8.767 | 2.865 | 0.645 | 16.496 | 0.868 | 0.935 | 0.033 | 0.000 | 3.859 | 26.588 |
| bagging+matching+geofence | 326981.000 | 307814.000 | 8.649 | 2.905 | 0.649 | 2.676 | 0.878 | 0.933 | 0.034 | 0.627 | 3.809 | 26.830 |

## Stressed vs ordinary days

| day_type | policy | orders | delivered | cost_per_delivered | orders_per_rider_hour | utilization | fake_accepted_per_1k | on_time_share_of_orders | on_time_share_of_delivered | cancel_rate | false_flags_per_1k | km_per_delivered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ordinary weekday | baseline | 125715.000 | 118815.000 | 9.715 | 2.617 | 0.660 | 17.086 | 0.747 | 0.791 | 0.015 | 0.000 | 4.511 |
| ordinary weekday | bagging | 125715.000 | 119884.000 | 9.553 | 2.640 | 0.623 | 16.840 | 0.909 | 0.953 | 0.007 | 0.000 | 4.151 |
| ordinary weekday | matching | 125715.000 | 118820.000 | 9.634 | 2.617 | 0.651 | 16.903 | 0.839 | 0.887 | 0.015 | 0.000 | 4.460 |
| ordinary weekday | bagging+matching | 125715.000 | 119741.000 | 9.490 | 2.637 | 0.620 | 17.007 | 0.922 | 0.968 | 0.008 | 0.000 | 4.155 |
| ordinary weekday | bagging+matching+geofence | 125715.000 | 121527.000 | 9.355 | 2.676 | 0.624 | 2.720 | 0.934 | 0.966 | 0.008 | 0.652 | 4.105 |
| rain day | baseline | 16817.000 | 9298.000 | 10.421 | 2.457 | 0.954 | 9.990 | 0.093 | 0.167 | 0.425 | 0.000 | 4.447 |
| rain day | bagging | 16817.000 | 12270.000 | 7.889 | 3.243 | 0.955 | 12.190 | 0.179 | 0.245 | 0.241 | 0.000 | 3.265 |
| rain day | matching | 16817.000 | 11693.000 | 8.187 | 3.090 | 0.932 | 12.012 | 0.269 | 0.387 | 0.276 | 0.000 | 3.361 |
| rain day | bagging+matching | 16817.000 | 13957.000 | 6.898 | 3.688 | 0.940 | 13.082 | 0.588 | 0.709 | 0.138 | 0.000 | 2.773 |
| rain day | bagging+matching+geofence | 16817.000 | 14089.000 | 6.835 | 3.723 | 0.942 | 3.033 | 0.593 | 0.708 | 0.140 | 0.714 | 2.742 |
| weekend or Ramadan | baseline | 184449.000 | 149772.000 | 9.655 | 2.639 | 0.673 | 14.215 | 0.483 | 0.595 | 0.154 | 0.000 | 4.524 |
| weekend or Ramadan | bagging | 184449.000 | 167582.000 | 8.593 | 2.952 | 0.652 | 15.842 | 0.749 | 0.824 | 0.054 | 0.000 | 3.824 |
| weekend or Ramadan | matching | 184449.000 | 156214.000 | 9.157 | 2.752 | 0.659 | 15.733 | 0.625 | 0.738 | 0.117 | 0.000 | 4.222 |
| weekend or Ramadan | bagging+matching | 184449.000 | 169868.000 | 8.412 | 2.993 | 0.645 | 16.460 | 0.857 | 0.930 | 0.041 | 0.000 | 3.739 |
| weekend or Ramadan | bagging+matching+geofence | 184449.000 | 172198.000 | 8.299 | 3.034 | 0.649 | 2.613 | 0.866 | 0.928 | 0.042 | 0.602 | 3.688 |

## A/B readout (hub-level randomisation)

| metric | control | treatment | diff | rel_diff | welch_lo | welch_hi | welch_p | boot_lo | boot_hi | direction | true_effect_all_hubs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cost_per_delivered | 9.7910 | 8.7496 | -1.0414 | -0.1064 | -1.4656 | -0.6172 | 0.0001 | -1.4052 | -0.6512 | lower is better | -1.0387 |
| orders_per_rider_hour | 2.5940 | 2.8945 | 0.3005 | 0.1158 | 0.1773 | 0.4236 | 0.0001 | 0.1871 | 0.4092 | higher is better | 0.2759 |
| utilization | 0.6670 | 0.6503 | -0.0167 | -0.0250 | -0.0405 | 0.0071 | 0.1599 | -0.0388 | 0.0041 | higher is better | -0.0264 |
| fake_accepted_per_1k | 11.7444 | 3.2365 | -8.5079 | -0.7244 | -15.0030 | -2.0127 | 0.0141 | -14.4313 | -2.9133 | lower is better | -12.1988 |
| on_time_share_of_orders | 0.5798 | 0.8624 | 0.2827 | 0.4875 | 0.2349 | 0.3304 | 0.0000 | 0.2413 | 0.3258 | higher is better | 0.3009 |
| cancel_rate | 0.1164 | 0.0375 | -0.0789 | -0.6780 | -0.0970 | -0.0608 | 0.0000 | -0.0962 | -0.0638 | lower is better | -0.0788 |
| lead_p90 | 41.1528 | 27.1501 | -14.0027 | -0.3403 | -16.4128 | -11.5925 | 0.0000 | -16.2220 | -11.8582 | lower is better | -15.0810 |

## Power (from the pre-period)

| metric | pre_mean | between_hub_sd | mde_80pct_power | mde_rel | true_effect | hubs_per_arm_needed |
|---|---|---|---|---|---|---|
| cost_per_delivered | 9.6204 | 0.5052 | 0.5788 | 0.0602 | -1.0387 | 5 |
| orders_per_rider_hour | 2.6553 | 0.1406 | 0.1611 | 0.0607 | 0.2759 | 6 |
| utilization | 0.6693 | 0.0334 | 0.0383 | 0.0572 | -0.0264 | 27 |
| fake_accepted_per_1k | 16.5203 | 13.6394 | 15.6255 | 0.9458 | -12.1988 | 21 |
| on_time_share_of_orders | 0.7110 | 0.0653 | 0.0748 | 0.1053 | 0.3009 | 3 |
| cancel_rate | 0.0245 | 0.0119 | 0.0136 | 0.5560 | -0.0788 | 2 |
| lead_p90 | 35.8870 | 3.8889 | 4.4552 | 0.1241 | -15.0810 | 3 |

## Re-randomisation check of the CIs

| metric | true_effect | welch_coverage | bootstrap_coverage | welch_power | aa_false_positive_welch | aa_false_positive_bootstrap | draws |
|---|---|---|---|---|---|---|---|
| cost_per_delivered | -1.039 | 0.984 | 0.972 | 1.000 | 0.026 | 0.042 | 500 |
| orders_per_rider_hour | 0.276 | 0.972 | 0.964 | 1.000 | 0.038 | 0.052 | 500 |
| utilization | -0.026 | 0.976 | 0.964 | 0.618 | 0.020 | 0.038 | 500 |
| fake_accepted_per_1k | -12.199 | 0.978 | 0.972 | 1.000 | 0.038 | 0.048 | 500 |
| on_time_share_of_orders | 0.301 | 0.986 | 0.978 | 1.000 | 0.050 | 0.090 | 500 |
| cancel_rate | -0.079 | 0.992 | 0.988 | 1.000 | 0.020 | 0.038 | 500 |
| lead_p90 | -15.081 | 0.988 | 0.968 | 1.000 | 0.072 | 0.078 | 500 |

## Geofence

| slice | events | fake | genuine | flagged | precision | recall | false_flag_rate |
|---|---|---|---|---|---|---|---|
| all | 11566 | 4938 | 6628 | 4287 | 0.956 | 0.830 | 0.028 |
| building=highrise | 4757 | 1684 | 3073 | 1543 | 0.895 | 0.820 | 0.053 |
| building=lowrise | 3054 | 1448 | 1606 | 1228 | 0.986 | 0.836 | 0.011 |
| building=villa | 3634 | 1749 | 1885 | 1466 | 0.995 | 0.834 | 0.004 |
| building=unknown | 121 | 57 | 64 | 50 | 0.980 | 0.860 | 0.016 |
| fake marked <300 m | 2629 | 2629 | 0 | 1791 | 1.000 | 0.681 | nan |
| fake marked 300-1000 m | 1667 | 1667 | 0 | 1667 | 1.000 | 1.000 | nan |
| fake marked >1 km | 642 | 642 | 0 | 642 | 1.000 | 1.000 | nan |

| radius_m | events | fake | genuine | flagged | precision | recall | false_flag_rate |
|---|---|---|---|---|---|---|---|
| 50.000 | 11566.000 | 4938.000 | 6628.000 | 5075.000 | 0.952 | 0.979 | 0.037 |
| 75.000 | 11566.000 | 4938.000 | 6628.000 | 4913.000 | 0.951 | 0.946 | 0.036 |
| 100.000 | 11566.000 | 4938.000 | 6628.000 | 4738.000 | 0.951 | 0.913 | 0.035 |
| 150.000 | 11566.000 | 4938.000 | 6628.000 | 4287.000 | 0.956 | 0.830 | 0.028 |
| 200.000 | 11566.000 | 4938.000 | 6628.000 | 3819.000 | 0.967 | 0.748 | 0.019 |
| 300.000 | 11566.000 | 4938.000 | 6628.000 | 3200.000 | 0.989 | 0.641 | 0.005 |
| 500.000 | 11566.000 | 4938.000 | 6628.000 | 2329.000 | 1.000 | 0.472 | 0.000 |
