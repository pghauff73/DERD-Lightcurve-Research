# EH Lib reproduction gate

The paper's page-7 figure labels the period as `0.0879 +/- 0.0002 days`. The historical
repository reports an approximately 99.6 percent match, but the current evidence capsule
does not contain the exact raw observation identity or a mathematical definition of that
percentage.

`EH_LIB_REPRODUCTION_CONTRACT.json` therefore records a blocked gate. It is not a failed
reproduction and it is not a reproduced result. The gate opens only after the exact source
file, passband, preprocessing, period/epoch policy, model version, metric, and holdout
status are frozen and checksummed.
