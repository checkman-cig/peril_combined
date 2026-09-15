-- CREATE TABLE policy_TIV_forWF_CAT_dedup AS
-- SELECT t.*
-- FROM policy_TIV_forWF_CAT t
-- JOIN (
--     SELECT
--         policy_search_nbr,
--         term_effective_date,
--         term_expiration_date,
--         business_line,
--         MAX(dec_policy) AS dec_policy
--     FROM policy_TIV_forWF_CAT
--     GROUP BY
--         policy_search_nbr,
--         term_effective_date,
--         term_expiration_date,
--         business_line
-- ) x
--     ON t.policy_search_nbr = x.policy_search_nbr
--    AND t.term_effective_date = x.term_effective_date
--    AND t.term_expiration_date = x.term_expiration_date
--    AND t.business_line = x.business_line
--    AND t.dec_policy = x.dec_policy;




BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE policy_peril_dedup PURGE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/

CREATE TABLE policy_peril_dedup AS
WITH key_fallback AS (
    SELECT
        policy_search_nbr,
        term_effective_date,
        term_expiration_date,
        business_line,
        COUNT(DISTINCT building_key) AS valid_building_key_count,
        MAX(building_key) AS fallback_building_key,
        MAX(claim_key) AS fallback_claim_key
    FROM POLICY_PERIL
    WHERE building_key IS NOT NULL
    GROUP BY
        policy_search_nbr,
        term_effective_date,
        term_expiration_date,
        business_line
)

SELECT
    t.*,
    k.valid_building_key_count,
    k.fallback_building_key,
    k.fallback_claim_key
FROM POLICY_PERIL t
JOIN (
    SELECT
        policy_search_nbr,
        term_effective_date,
        term_expiration_date,
        business_line,
        MAX(dec_policy) AS dec_policy
    FROM POLICY_PERIL
    GROUP BY
        policy_search_nbr,
        term_effective_date,
        term_expiration_date,
        business_line
) x
    ON t.policy_search_nbr = x.policy_search_nbr
   AND t.term_effective_date = x.term_effective_date
   AND t.term_expiration_date = x.term_expiration_date
   AND t.business_line = x.business_line
   AND t.dec_policy = x.dec_policy
JOIN (
    SELECT
        dec_policy,
        unit_key,
        SUM(NVL(inforce_prem, 0)) AS total_unit_prem
    FROM prem
    GROUP BY
        dec_policy,
        unit_key
) p
    ON t.dec_policy = p.dec_policy
   AND t.unit_key = p.unit_key
LEFT JOIN key_fallback k
    ON t.policy_search_nbr = k.policy_search_nbr
   AND t.term_effective_date = k.term_effective_date
   AND t.term_expiration_date = k.term_expiration_date
   AND t.business_line = k.business_line
WHERE
       NVL(p.total_unit_prem, 0) > 0
    OR t.dec_type IN ('Cancel', 'Non-Renew')
    OR t.cancel_effective_date IS NOT NULL
    OR t.nonrenew_effective_date IS NOT NULL;



UPDATE policy_peril_dedup
SET
    building_key = fallback_building_key,
    claim_key = fallback_claim_key
WHERE building_key IS NULL
  AND valid_building_key_count = 1;


ALTER TABLE policy_peril_dedup DROP COLUMN valid_building_key_count;
ALTER TABLE policy_peril_dedup DROP COLUMN fallback_building_key;
ALTER TABLE policy_peril_dedup DROP COLUMN fallback_claim_key;
ALTER TABLE policy_peril_dedup DROP COLUMN total_unit_prem;
ALTER TABLE policy_peril_dedup DROP COLUMN rn;


-- CREATE TABLE policy_TIV_forWF_CAT_dedup AS
-- SELECT t.*
-- FROM policy_TIV_forWF_CAT t
-- JOIN (
--     SELECT
--         policy_search_nbr,
--         term_effective_date,
--         term_expiration_date,
--         business_line,
--         MAX(dec_policy) AS dec_policy
--     FROM policy_TIV_forWF_CAT
--     GROUP BY
--         policy_search_nbr,
--         term_effective_date,
--         term_expiration_date,
--         business_line
-- ) x
--     ON t.policy_search_nbr = x.policy_search_nbr
--    AND t.term_effective_date = x.term_effective_date
--    AND t.term_expiration_date = x.term_expiration_date
--    AND t.business_line = x.business_line
--    AND t.dec_policy = x.dec_policy
-- JOIN (
--     SELECT
--         dec_policy,
--         unit_key,
--         SUM(NVL(inforce_prem, 0)) AS total_unit_prem
--     FROM prem
--     GROUP BY dec_policy, unit_key
-- ) p
--     ON t.dec_policy = p.dec_policy
--    AND t.unit_key = p.unit_key
-- WHERE
--        NVL(p.total_unit_prem, 0) > 0
--     OR t.dec_type IN ('Cancel', 'Non-Renew')
--     OR t.cancel_effective_date IS NOT NULL
--     OR t.nonrenew_effective_date IS NOT NULL;


-- CREATE TABLE policy_TIV_forWF_CAT_dedup AS
-- SELECT t.*
-- FROM policy_TIV_forWF_CAT t
-- JOIN (
--     SELECT
--         policy_search_nbr,
--         term_effective_date,
--         term_expiration_date,
--         business_line,
--         MAX(dec_policy) AS dec_policy
--     FROM policy_TIV_forWF_CAT
--     GROUP BY
--         policy_search_nbr,
--         term_effective_date,
--         term_expiration_date,
--         business_line
-- ) x
--     ON t.policy_search_nbr = x.policy_search_nbr
--    AND t.term_effective_date = x.term_effective_date
--    AND t.term_expiration_date = x.term_expiration_date
--    AND t.business_line = x.business_line
--    AND t.dec_policy = x.dec_policy
-- JOIN (
--     SELECT
--         dec_policy,
--         unit_key,
--         SUM(NVL(inforce_prem, 0)) AS total_unit_prem
--     FROM prem
--     GROUP BY
--         dec_policy,
--         unit_key
--     HAVING SUM(NVL(inforce_prem, 0)) > 0
-- ) p
--     ON t.dec_policy = p.dec_policy;
--     -- AND NVL(TO_CHAR(t.property_addr_nbr), 'NO_MATCH') = NVL(TO_CHAR(p.unit_key), 'NO_MATCH');






-- If i pull in term_nbr
-- CREATE TABLE policy_TIV_forWF_CAT_dedup AS
-- SELECT t.*
-- FROM policy_TIV_forWF_CAT t
-- JOIN (
--     SELECT
--         policy_search_nbr,
--         term_nbr,
--         business_line,
--         MAX(dec_policy) AS dec_policy
--     FROM policy_TIV_forWF_CAT
--     GROUP BY
--         policy_search_nbr,
--         term_nbr,
--         business_line
-- ) x
--     ON t.policy_search_nbr = x.policy_search_nbr
--    AND t.term_nbr = x.term_nbr
--    AND t.business_line = x.business_line
--    AND t.dec_policy = x.dec_policy
-- JOIN (
--     SELECT
--         dec_policy,
--         unit_key,
--         SUM(NVL(inforce_prem, 0)) AS total_unit_prem
--     FROM prem
--     GROUP BY
--         dec_policy,
--         unit_key
--     HAVING SUM(NVL(inforce_prem, 0)) > 0
-- ) p
--     ON t.dec_policy = p.dec_policy
--    AND t.unit_key = p.unit_key
