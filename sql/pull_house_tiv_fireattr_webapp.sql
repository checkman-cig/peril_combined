BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE policy_peril PURGE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/

CREATE TABLE policy_peril AS
WITH ho_property_info AS (
    SELECT
        dp_echo.dec_policy,
        ho.*
    FROM policy bound_policy
    JOIN policy quote_policy
        ON bound_policy.online_ref_number = quote_policy.online_ref_number
       AND quote_policy.quote_flag = 1
    JOIN webapp.app_ho_property_info ho
        ON quote_policy.policy = ho.policy
    JOIN dec_policy dp_echo
        ON bound_policy.policy = dp_echo.policy
    WHERE bound_policy.quote_flag = 0
)

SELECT
    dp.dec_policy,
    dp.business_line,
    dp.policy_search_nbr,
    p.unit_key,

    CASE 
        WHEN dp.business_line = 'Homeowner' AND dh.homeowner_unit IS NOT NULL THEN 'dh_' || TO_CHAR(dh.homeowner_unit)
        WHEN dp.business_line = 'Dwelling Fire' AND df.dwelling_fire IS NOT NULL THEN 'df_' || TO_CHAR(df.dwelling_fire)
    END AS building_key,

    CASE 
        WHEN dp.business_line = 'Homeowner' AND dh.dec_home IS NOT NULL THEN 'DEC_HOME_' || TO_CHAR(dh.dec_home)
        WHEN dp.business_line = 'Dwelling Fire' AND df.dec_dwelling_fire IS NOT NULL THEN 'DEC_DWELLING_FIRE_' || TO_CHAR(df.dec_dwelling_fire)
    END AS claim_key,

    dp.policy_status,
    dp.dec_type,
    dp.term_effective_date,
    dp.term_expiration_date,

    CASE
        WHEN pol.cancel_effective_date <= DATE '1900-01-01'
        THEN NULL
        ELSE pol.cancel_effective_date
    END AS cancel_effective_date,
    
    pol.nonrenew_effective_date,

    LEAST(
        NVL(
            CASE
                WHEN pol.cancel_effective_date <= DATE '1900-01-01'
                THEN NULL
                ELSE pol.cancel_effective_date
            END,
            dp.term_expiration_date
        ),
        NVL(pol.nonrenew_effective_date, dp.term_expiration_date),
        dp.term_expiration_date
    ) AS corrected_expiration_date,

    dp.term_nbr,

    CASE 
        WHEN dp.business_line = 'Homeowner' THEN dh.property_addr_nbr
        WHEN dp.business_line = 'Dwelling Fire' THEN df.property_addr_nbr
    END AS property_addr_nbr,

    CASE 
        WHEN dp.business_line = 'Homeowner' THEN dh.property_street_name
        WHEN dp.business_line = 'Dwelling Fire' THEN df.property_street_name
    END AS property_street_name,

    CASE 
        WHEN dp.business_line = 'Homeowner' THEN dh.property_city
        WHEN dp.business_line = 'Dwelling Fire' THEN df.property_city
    END AS property_city,

    CASE 
        WHEN dp.business_line = 'Homeowner' THEN dh.property_state
        WHEN dp.business_line = 'Dwelling Fire' THEN df.property_state
    END AS property_state,

    CASE 
        WHEN dp.business_line = 'Homeowner' THEN dh.property_zipcode
        WHEN dp.business_line = 'Dwelling Fire' THEN df.property_zipcode
    END AS property_zipcode,

    dp.agency_domicile_state,

    /* Base coverage fields */
    NVL(NVL(dh.dwelling_limit, df.dwelling_limit), 0) AS property_limit,
    NVL(NVL(dh.dwelling_limit, df.dwelling_limit), 0) AS "Cov. A - Dwelling",

    NVL(dh.structure_limit, 0) AS appt_struct,
    NVL(NVL(dh.structure_limit, ROUND(NVL(df.dwelling_limit, 0) * 0.10)), 0) AS "Cov. B - Other Structures",

    NVL(NVL(dh.property_limit, df.contents_limit), 0) AS contents_limit,
    NVL(NVL(dh.property_limit, df.contents_limit), 0) AS "Cov. C - Personal Property",

    NVL(dh.loss_of_use_limit, 0) AS "Cov. D (HO) - Loss of Use",
    ROUND(NVL(df.dwelling_limit, 0) * 0.10) AS "Cov. D (DF) - Fair Rental",

    -- NVL(NVL(dh.liability_limit, df.liability_limit), '0') AS "Cov. E - Personal Liability"
    -- This had to be edited becuase df.liability limit had both text and numbers
    NVL(
        NVL(
            dh.liability_limit,
            TO_NUMBER(REGEXP_REPLACE(df.liability_limit, '[^0-9.]'))
        ),
        0
    ) AS "Cov. E - Personal Liability",

   NVL(
       NVL(
           TO_CHAR(dh.medical_limit),
           df.medpay_per_person_limit || '/' || df.medpay_per_occ_limit
       ),
       '0'
   ) AS "Cov. F - Medical Payments",

    NVL(
        NVL(
            dh.loss_of_use_limit,
            ROUND(NVL(df.dwelling_limit, 0) * 0.10)
        ),
        0
    ) AS add_liv_exps,

    /* TIV */
    CASE
        WHEN dp.business_line = 'Homeowner' THEN
            ROUND(
                NVL(dh.dwelling_limit, 0)
              + NVL(dh.structure_limit, 0)
              + NVL(dh.property_limit, 0)
              + NVL(dh.loss_of_use_limit, 0)
              + NVL(
                    CASE
                        WHEN dp.agency_domicile_state IN ('CA', 'OR', 'WA') THEN
                            NVL(dh.drc_coverage, 0) * 0.5 * NVL(dh.dwelling_limit, 0)
                        WHEN dp.agency_domicile_state = 'NV' THEN
                            NVL(dh.drc_coverage, 0) * 1.0 * NVL(dh.dwelling_limit, 0)
                        ELSE 0
                    END,
                    0
                )
            )

        WHEN dp.business_line = 'Dwelling Fire' THEN
            ROUND(
                NVL(df.dwelling_limit, 0)
              + NVL(df.dwelling_limit * 0.10, 0)
              + NVL(df.contents_limit, 0)
              + NVL(df.dwelling_limit * 0.10, 0)
              + NVL(
                    CASE
                        WHEN dp.agency_domicile_state IN ('CA', 'WA') THEN
                            NVL(df.drc_coverage, 0) * 0.5 * NVL(df.dwelling_limit, 0)
                        WHEN dp.agency_domicile_state IN ('NV', 'OR') THEN
                            NVL(df.drc_coverage, 0) * 1.0 * NVL(df.dwelling_limit, 0)
                        ELSE 0
                    END,
                    0
                )
            )
        ELSE 0
    END AS tiv,

    /* Extended Replacement Coverage */
    CASE
        WHEN dp.business_line = 'Homeowner' THEN
            CASE
                WHEN dp.agency_domicile_state IN ('CA', 'OR', 'WA') THEN
                    NVL(dh.drc_coverage, 0) * 0.5 * NVL(dh.dwelling_limit, 0)
                WHEN dp.agency_domicile_state = 'NV' THEN
                    NVL(dh.drc_coverage, 0) * 1.0 * NVL(dh.dwelling_limit, 0)
                ELSE 0
            END

        WHEN dp.business_line = 'Dwelling Fire' THEN
            CASE
                WHEN dp.agency_domicile_state IN ('CA', 'WA') THEN
                    NVL(df.drc_coverage, 0) * 0.5 * NVL(df.dwelling_limit, 0)
                WHEN dp.agency_domicile_state IN ('NV', 'OR') THEN
                    NVL(df.drc_coverage, 0) * 1.0 * NVL(df.dwelling_limit, 0)
                ELSE 0
            END
        ELSE 0
    END AS "Extended Replacement Cov",

    /* Other derived fields */
    CASE
        WHEN NVL(dh.ho5, 0) = 1 THEN NVL(dh.dwelling_limit, 0) * 0.10
        ELSE NVL(dh.dwelling_limit, 0) * 0.05
    END AS "Debris Removal Cov",

    NVL(dh.dwelling_limit, 0) * 0.05 AS "Trees and Shrubs",

    /* Optional coverages */
    NVL(NVL(dh.drc_coverage, df.drc_coverage), 0) AS drc_coverage,
    NVL(NVL(dh.cal_pak_coverage, 0), 0) AS cal_pak_coverage,
    NVL(NVL(dh.dic, df.dic), 0) AS dic_coverage,
    NVL(NVL(dh.ord_law_coverage, df.ord_law_coverage), 0) AS ord_law_coverage,
    NVL(NVL(dh.eq_deductible, df.eq_coverage), 'Not Specified') AS eq_coverage,
    NVL(NVL(dh.appliance_breakdown, df.appliance_breakdown), 0) AS "Appliance Breakdown Ends",
    NVL(NVL(dh.service_line_endorsement, df.service_line_endorsement), 0) AS "Service Line Ends",

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.CONSTRUCTION_TYPE
    WHEN dp.business_line = 'Dwelling Fire' THEN df.CONSTRUCTION_TYPE
END AS CONSTRUCTION_TYPE,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN TO_CHAR(dh.CONSTRUCTION_YEAR)
    WHEN dp.business_line = 'Dwelling Fire' THEN TO_CHAR(df.CONSTRUCTION_YEAR)
END AS CONSTRUCTION_YEAR,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.ROOF_TYPE
    WHEN dp.business_line = 'Dwelling Fire' THEN df.ROOF_TYPE
END AS ROOF_TYPE,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.PROTECTION_CLASS
    WHEN dp.business_line = 'Dwelling Fire' THEN df.PROTECTION_CLASS
END AS PROTECTION_CLASS,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.BRUSH_AREA
    WHEN dp.business_line = 'Dwelling Fire' THEN df.BRUSH_AREA
END AS BRUSH_AREA,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.SQ_FT_DWELLING
    WHEN dp.business_line = 'Dwelling Fire' THEN df.SQ_FT_DWELLING
END AS SQ_FT_DWELLING,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.FIRE_STATION_MILES
    WHEN dp.business_line = 'Dwelling Fire' THEN df.FIRE_STATION_MILES
END AS FIRE_STATION_MILES,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.HYDRANT_FEET
    WHEN dp.business_line = 'Dwelling Fire' THEN df.HYDRANT_FEET
END AS HYDRANT_FEET,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.FIRE_RISK_COMMUNITY_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.FIRE_RISK_COMMUNITY_DISC
END AS FIRE_RISK_COMMUNITY_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.FIREWISE_COMMUNITY_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.FIREWISE_COMMUNITY_DISC
END AS FIREWISE_COMMUNITY_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.CLEARING_UNDER_DECKS_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.CLEARING_UNDER_DECKS_DISC
END AS CLEARING_UNDER_DECKS_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.FIVE_FOOT_CLEARANCE_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.FIVE_FOOT_CLEARANCE_DISC
END AS FIVE_FOOT_CLEARANCE_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.NONCOMBUSTIBLE_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.NONCOMBUSTIBLE_DISC
END AS NONCOMBUSTIBLE_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.COMBUSTIBLE_REMOVAL_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.COMBUSTIBLE_REMOVAL_DISC
END AS COMBUSTIBLE_REMOVAL_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.DEFENSIBLE_SPACE_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.DEFENSIBLE_SPACE_DISC
END AS DEFENSIBLE_SPACE_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.COMBINED_CLEARING_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.COMBINED_CLEARING_DISC
END AS COMBINED_CLEARING_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.ROOFING_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.ROOFING_DISC
END AS ROOFING_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.ENCLOSED_EAVES_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.ENCLOSED_EAVES_DISC
END AS ENCLOSED_EAVES_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.FIRE_RESISTANT_VENTS_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.FIRE_RESISTANT_VENTS_DISC
END AS FIRE_RESISTANT_VENTS_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.MULTI_PANED_WINDOWS_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.MULTI_PANED_WINDOWS_DISC
END AS MULTI_PANED_WINDOWS_DISC,

CASE 
    WHEN dp.business_line = 'Homeowner' THEN dh.VERTICAL_CLEARANCE_DISC
    WHEN dp.business_line = 'Dwelling Fire' THEN df.VERTICAL_CLEARANCE_DISC
END AS VERTICAL_CLEARANCE_DISC, 

    ho.residence_type AS residence_type,
    ho.occupant AS occupant,
    ho.structure_type AS structure_type,
    ho.foundation AS foundation,
    ho.fire_station_miles AS ho_fire_station_miles,
    ho.fireplace_spark_arrestor AS fireplace_spark_arrestor,
    ho.nbr_of_years_insured AS nbr_of_years_insured,
    ho.central_alarm_type AS central_alarm_type,
    ho.nbr_active_df_policies AS nbr_active_df_policies

FROM dec_policy dp
JOIN (
    SELECT
        dec_policy,
        unit_key,
        SUM(NVL(inforce_prem,0)) AS prem1
    FROM prem
    GROUP BY dec_policy, unit_key
) p
    ON dp.dec_policy = p.dec_policy
JOIN policy pol
    ON dp.policy_search_nbr = pol.policy_search_nbr
LEFT JOIN dec_home dh
    ON dp.dec_policy = dh.dec_policy
   AND p.unit_key = dh.dec_home
LEFT JOIN dec_dwelling_fire df
    ON dp.dec_policy = df.dec_policy
   AND p.unit_key = df.dec_dwelling_fire
LEFT JOIN ho_property_info ho
    ON dp.dec_policy = ho.dec_policy
WHERE dp.business_line IN ('Homeowner', 'Dwelling Fire')
    AND dp.policy_status IN ('Canceled', 'Active', 'Non-Renewed')
    AND dp.term_effective_date >= DATE '1995-01-01'