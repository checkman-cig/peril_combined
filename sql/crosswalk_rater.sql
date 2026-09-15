DROP TABLE crosswalk_rater;

CREATE TABLE crosswalk_rater AS

SELECT
    dp.policy_search_nbr,
    dp.dec_policy,
    dh.dec_home AS risk_unit_key,
    'dh_' || TO_CHAR(dh.homeowner_unit) AS building_key
FROM dec_policy@echo.world dp
JOIN dec_home@echo.world dh
    ON dp.dec_policy = dh.dec_policy
WHERE dp.term_effective_date >= DATE '2000-01-01'

UNION ALL

SELECT
    dp.policy_search_nbr,
    dp.dec_policy,
    df.dec_dwelling_fire AS risk_unit_key,
    'df_' || TO_CHAR(df.dwelling_fire) AS building_key
FROM dec_policy@echo.world dp
JOIN dec_dwelling_fire@echo.world df
    ON dp.dec_policy = df.dec_policy
WHERE dp.term_effective_date >= DATE '2000-01-01';