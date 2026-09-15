/*Update Log*/
--prior version: "G:\Product Reviews\Rate Reviews\2022Q4\Prep\Indication Data Pull\Queries\Dwelling Fire\DF Loss with Perils - Updated Closed Date.sql"
--6/19/2023 (001) - AC: remove Baupost subrogation calculation adjustment per Pam's request
--8/10/2023 (002) - AC: Revised CLOSING_QTR logic and updated for Claim Center
--2/1/2024 (003) - AL: fixed Claim Center logic, however, note that peril assignment may not be fixed for Claim Center data yet, added source to remove dups in first join



/*Loss Data*/
/*
Unit-level update:
Adds claim_key, building_key, and unit_match_method. Joins DEC_DWELLING_FIRE by resolved
claim unit instead of aggregating all DEC_DWELLING_FIRE rows on dec_policy.

Unit-resolution logic for Dwelling Fire claims.

Main route:
  CLMUSER.CLAIM_TRANSACTIONS.risk_unit_key + fixed risk table
  -> DEC_DWELLING_FIRE -> building_key

Fallback route:
  If claim_transactions does not provide one usable DEC_DWELLING_FIRE unit, but the
  claim's policy term has exactly one DEC_DWELLING_FIRE row, assign that single unit.
*/


BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE peril_loss_unit_DF PURGE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/


CREATE TABLE peril_loss_unit_DF AS

WITH params AS (
    SELECT to_date('31-Dec-2025 11:59:59 PM',
                   'dd-mon-yyyy hh:mi:ss PM',
                   'NLS_DATE_LANGUAGE=ENGLISH') AS experience_period
    FROM dual
),


ct_fixed AS (
    SELECT
        ct.claim_source,
        ct.claim_number,
        ct.policy_number,
        ct.risk_unit_key,
        CASE
            WHEN ct.risk_location_table IS NOT NULL
                THEN TO_CHAR(ct.risk_location_table)
            WHEN REGEXP_SUBSTR(ct.policy_number, '[^-]+', 1, 2) = 'DFC'
                THEN 'DEC_DWELLING_FIRE'
        END AS risk_table_fixed
    FROM clmuser.claim_transactions ct
),

/* Keep the existing coverage_type helper from claim_transactions. */
ct_coverage AS (
    SELECT
        MAX(coverage_type) AS coverage_type,
        claim_source,
        claim_number
    FROM clmuser.claim_transactions
    GROUP BY claim_source, claim_number
),

/* Main route: transaction unit key maps directly to DEC_DWELLING_FIRE. */
ct_dwelling_fire_unit AS (
    SELECT
        ct.claim_source,
        ct.claim_number,
        COUNT(DISTINCT ddf.dec_dwelling_fire) AS dec_dwelling_fire_cnt,
        MAX(ddf.dec_dwelling_fire) AS dec_dwelling_fire,
        MAX('DEC_DWELLING_FIRE_' || TO_CHAR(ddf.dec_dwelling_fire)) AS claim_key,
        MAX('df_' || TO_CHAR(ddf.dwelling_fire)) AS building_key
    FROM ct_fixed ct
    JOIN dec_dwelling_fire@echo.world ddf
        ON ct.risk_table_fixed = 'DEC_DWELLING_FIRE'
       AND ct.risk_unit_key = ddf.dec_dwelling_fire
    WHERE ct.risk_unit_key IS NOT NULL
    GROUP BY
        ct.claim_source,
        ct.claim_number
),

/* Fallback route: only use policy DEC_DWELLING_FIRE when exactly one unit exists. */
policy_single_dwelling_fire AS (
    SELECT
        ddf.dec_policy,
        COUNT(DISTINCT ddf.dec_dwelling_fire) AS dec_dwelling_fire_cnt,
        MAX(ddf.dec_dwelling_fire) AS dec_dwelling_fire,
        MAX('DEC_DWELLING_FIRE_' || TO_CHAR(ddf.dec_dwelling_fire)) AS claim_key,
        MAX('df_' || TO_CHAR(ddf.dwelling_fire)) AS building_key
    FROM dec_dwelling_fire@echo.world ddf
    GROUP BY ddf.dec_policy
),

resolved_dwelling_fire_unit AS (
    SELECT DISTINCT
        cl.source,
        cl.claim_nbr,
        COALESCE(ctu.dec_dwelling_fire, psdf.dec_dwelling_fire) AS resolved_dec_dwelling_fire,
        COALESCE(ctu.claim_key, psdf.claim_key) AS claim_key,
        COALESCE(ctu.building_key, psdf.building_key) AS building_key,
        CASE
            WHEN ctu.dec_dwelling_fire_cnt = 1
                THEN 'claim_transactions'
            WHEN ctu.dec_dwelling_fire_cnt IS NULL
             AND psdf.dec_dwelling_fire_cnt = 1
                THEN 'single_dwelling_fire_fallback'
            ELSE 'unassigned'
        END AS unit_match_method
    FROM clmuser.claim_info cl
    LEFT JOIN ct_dwelling_fire_unit ctu
        ON cl.source = ctu.claim_source
       AND cl.claim_nbr = ctu.claim_number
       AND ctu.dec_dwelling_fire_cnt = 1
    LEFT JOIN policy_single_dwelling_fire psdf
        ON cl.dec_policy = psdf.dec_policy
       AND psdf.dec_dwelling_fire_cnt = 1
)

select 
       extract(year from dl.trans_date) C_YEAR,
       extract(year from cl.date_of_loss) A_YEAR,
       cl.date_of_loss,
       case when extract(month from dl.trans_date) in (1,2,3) then to_date('31-Mar-'||extract(year from dl.trans_date),'dd-mon-yyyy')
            when extract(month from dl.trans_date) in (4,5,6) then to_date('30-Jun-'||extract(year from dl.trans_date),'dd-mon-yyyy')
            when extract(month from dl.trans_date) in (7,8,9) then to_date('30-Sep-'||extract(year from dl.trans_date),'dd-mon-yyyy')
            else to_date('31-Dec-'||extract(year from dl.trans_date),'dd-mon-yyyy') end TRANS_QTR,
       case when extract(month from cl.first_modified) in (1,2,3) then to_date('31-Mar-'||extract(year from cl.first_modified),'dd-mon-yyyy')
            when extract(month from cl.first_modified) in (4,5,6) then to_date('30-Jun-'||extract(year from cl.first_modified),'dd-mon-yyyy')
            when extract(month from cl.first_modified) in (7,8,9) then to_date('30-Sep-'||extract(year from cl.first_modified),'dd-mon-yyyy')
            else to_date('31-Dec-'||extract(year from cl.first_modified),'dd-mon-yyyy') end OPENING_QTR,
       case when cl.claim_status = 'Closed' then
         case when extract(month from cl.claim_status_date) in (1,2,3) then to_date('31-Mar-'||extract(year from cl.claim_status_date),'dd-mon-yyyy')
              when extract(month from cl.claim_status_date) in (4,5,6) then to_date('30-Jun-'||extract(year from cl.claim_status_date),'dd-mon-yyyy')
              when extract(month from cl.claim_status_date) in (7,8,9) then to_date('30-Sep-'||extract(year from cl.claim_status_date),'dd-mon-yyyy')
              else to_date('31-Dec-'||extract(year from cl.claim_status_date),'dd-mon-yyyy') end            

         else null
         end CLOSING_QTR,
       cl.POLICY_SEARCH_NBR,
       rdfu.claim_key,              -- unit bridge key: DEC_DWELLING_FIRE_<dec_dwelling_fire>
       rdfu.building_key,           -- final DF unit/building key used for policy merge
       rdfu.unit_match_method,      -- claim_transactions or single_dwelling_fire_fallback
       cl.EFFECTIVE_DATE TERM_EFFECTIVE_DATE,
       dp.agency_code,
       dp.agency_name,
       a.domicile_state,
       dc.WRITING_COMPANY,
       case when dp.agency_code in (24949,26906,26907,26908,26910,26911,26914,
              26916,26917,26919,26922,26924,26946,26947,26949,26951,26961,27250,27251,27252,27901,27902,27903,
              27904,27905,27906,27908,27909,27911,27913,27916,27917,27918,27919,27922,27923,27924,27925,27945,
              27946,27947,27959,27961,47141,47179,47212,47222,47225,47247,49951,50018,50022,50023,50024,50025,
              50035,50038,50039,50042,50043,50046,50048,50049,50051,50053,50054,50056,50105,50147,50161,50950,
              50951,50952,71000,71001,71002,71005,71006,71008,71009,71010,71011,71012,71013,71015,71016,71017,
              71018,71019,71020,71021,71022,71023,71024,71025,71025,71026,71027,71028,71029,71030,71031,71032,
              71033,71034,71035,71036,71037,71038,71039,71040,71041,71042,71044,71045,71046,71047,71048,71049,
              71050,71051,71052,71053,71054,71055,71056,71057,71058,71059,71060,71061,71062,71063,71070,71071,71072,71073) then 'Washington Branch'
            when dp.agency_code in (48060, 26700,26722,27710,47470,47471,55001,66180,66181,66182,66183,66410,66420,71504) then 'Alternative Markets Programs'
            else dp.branch_name end BRANCH_NAME,
       dp.branch_nbr,
       dp.business_line,
       dl.dept_nbr,
       dl.dept_desc,
       dl.a_s_line_nbr,
       dl.a_s_line_desc,
       dl.line_nbr,
       dl.coverage_line_desc COVERAGE,
       'Form '||ddf.policy_form POLICY_FORM,
       dc.claim_nbr,
       cl.claim,--warning, this is no longer unique, CMS and CC can have the same claim_key/claim_id
       cl.claim_status,
       decode(cl.catastrophe,null,'No','Yes') CATASTROPHE,
       sum(dl.loss_paid) LOSS_PAID,
       sum(dl.alloc_expense_paid) DCCE_PAID,
       sum(dl.alloc_expense_paid) + sum(dl.unalloc_expense_paid) ALAE_PAID,
       sum(dl.loss_paid) + sum(dl.alloc_expense_paid) LOSS_DCCE_PAID,
       sum(dl.loss_paid) + sum(dl.alloc_expense_paid) + sum(dl.unalloc_expense_paid) LOSS_ALAE_PAID,
       sum(dl.loss_reserve) LOSS_INCURRED,
       sum(dl.alloc_expense_reserve) DCCE_INCURRED,
       sum(dl.alloc_expense_reserve) + sum(dl.unalloc_expense_reserve) ALAE_INCURRED,
       sum(dl.loss_reserve) + sum(dl.alloc_expense_reserve) LOSS_DCCE_INCURRED,
       sum(dl.loss_reserve) + sum(dl.alloc_expense_reserve) + sum(dl.unalloc_expense_reserve) LOSS_ALAE_INCURRED,
       sum(0) SUBROGATION_ANTICIPATED, --AC: filler column after removing Baupost 6/19/23
       1.5 * nvl(ddf.dwelling_limit,0) + nvl(ddf.contents_limit,0) ADJ_ERC_LIMIT, --150% Dwelling + 10% Contents + 10% Loss of Use ---- 06/03/2026: BO changed 1.7 to 1.5. Need to verify when Cathy is back.
      case 
        -- when decode(cl.catastrophe,null,'No','Yes')='Yes' then 'CAT'
        when dl.cause_of_loss = 'Earthquake' then 'EQ'        
        when dl.coverage_line_desc = 'Bldg Ord' then 'ord law'
        when dl.coverage_line_desc in ('Cal Pak','2nd Cal Pak')  then 'cal pak'   
       -- when ct.coverage_type = 'Bldg Ord' then 'ord law'
        when ct.coverage_type = 'F. Medical Payments' then 'MEDPAY'
       -- when ct.coverage_type = 'Ordinance or Law' then 'ord law'  --this coverage is in addition to coverage A. 
       -- when ct.coverage_type = 'Identity Fraud' then 'Fraud?' --this is not a fraud targeting CIG. We paid for the claim, this is identity fraud against our insured.
       -- when ct.coverage_type = 'Quake' then 'EQ'
       -- when ct.coverage_type = 'Cal Pak' then 'cal pak(HO)'
        when ct.coverage_type = 'Coverage F - Medical Payments To Others' then 'MEDPAY'
        when dl.cause_group = '3rd Party Casualty' then 'Liability'
          when regexp_instr(upper(claim_desc), '(^|[^A-Z])LIGHTEN' , 1, 1) + regexp_instr(upper(claim_desc), '(^|[^A-Z])LIGHTN' , 1, 1) + instr(upper(claim_desc), 'THUNDER, LIGHTING,', 1, 1)  
          + regexp_instr(upper(claim_desc), '(^|[^A-Z])HAIL' , 1, 1) + regexp_instr(upper(claim_desc), '(^|[^A-Z])HALE' , 1, 1) > 0
                and regexp_instr(upper(claim_desc), '(^|[^A-Z])RAIN', 1, 1) + regexp_instr(upper(claim_desc), '(^|[^A-Z])WATER', 1, 1) +
                regexp_instr(upper(claim_desc), '(^|[^A-Z])WTR' , 1, 1) < 1
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
                then 'Non-Water Storm'
          when ((nvl(cwlf.backup,0)> 0) 
              or (regexp_instr(upper(claim_desc), '(^|[^A-Z])BACKUP', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])BACK UP', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])BACKING UP', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])BACKED UP', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])BACK-UP', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])OVERFLOW', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])OVER FLOW', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])CLOGGED', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])BLOCKAGE', 1, 1) > 0
               and regexp_instr(upper(claim_desc), '(^|[^A-Z])ROOF', 1, 1)
               + instr(upper(claim_desc), 'A/C', 1, 1)
               + instr(upper(claim_desc), 'AIR CONDITION' , 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])AC([^A-Z]|$)' , 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])FRIDGE' , 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])FRIGE' , 1, 1)
               = 0))
               and (col.water_flag > 0 or (col.structure_flag>0 and (regexp_instr(replace(upper(claim_desc), 'NO WATER DAMAGE','xxx'),'(^|[^A-Z])WATER', 1, 1) +
          regexp_instr(replace(upper(claim_desc), 'NO WTR DAMAGE','xxx'),'(^|[^A-Z])WTR', 1, 1)
          +regexp_instr(replace(upper(claim_desc),'GAS LEAK','xxx'), '(^|[^A-Z])LEAK', 1, 1)>0)))
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
               then 'Backup'
          when col.breakdown_flag
              + instr(upper(claim_desc), 'WATER HEAT' , 1, 1)
              + instr(upper(claim_desc), 'DISHWA' , 1, 1)
              + instr(upper(claim_desc), 'DISH WASHER' , 1, 1)
              + instr(upper(claim_desc), 'WASHING MACHINE' , 1, 1)
              + instr(upper(claim_desc), 'MALFUN' , 1, 1)
              --+ regexp_instr(upper(claim_desc), '(^|[^A-Z])A/C' , 1, 1) check this in the next breakdown case
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])BREAKDOWN' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])AIR CONDITION' , 1, 1)
              --+ regexp_instr(upper(claim_desc), '(^|[^A-Z])AC([^A-Z]|$)' , 1, 1) check this in the next breakdown case
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])FRIDGE' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])FRIGE' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])SUMP PUMP', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])SHORTED', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])COMPRESSOR', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])FREEZER BROKE DOWN', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])REFRIG BROKE DOWN', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])REFRIGERATOR BROKE DOWN', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])APPLIANCE', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])BROKE', 1, 1)
              + nvl(cwlf.breakdown,0) > 0
                and regexp_instr(upper(claim_desc), '(^|[^A-Z])PIPE' , 1, 1) -- there is one more breakdown case in the end. Just be cautious in this case to not assign non-breakdown cases here. Next breakdown case statement is less conservative. 
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])LINE' , 1, 1)
                + instr(upper(claim_desc), 'BACKED UP' , 1, 1)
                +regexp_instr(upper(claim_desc), '(^|[^A-Z])OVERFLOW' , 1, 1)
                +regexp_instr(upper(claim_desc), '(^|[^A-Z])WATER' , 1, 1)
                +regexp_instr(upper(claim_desc), '(^|[^A-Z])WTR' , 1, 1)
                +regexp_instr(upper(claim_desc), '(^|[^A-Z])LEAK' , 1, 1)
                +regexp_instr(upper(claim_desc), '(^|[^A-Z])HOSE' , 1, 1)
                +regexp_instr(upper(claim_desc), '(^|[^A-Z])BURST' , 1, 1)
                +regexp_instr(upper(claim_desc), '(^|[^A-Z])FLOOD' , 1, 1)
                = 0
                and col.theftvand_flag = 0 and col.FIRE_FLAG=0
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
                then 'Breakdown'
          when ((col.storm_flag > 0
                  and regexp_instr(upper(claim_desc), '(^|[^A-Z])RAIN', 1, 1)
                  +regexp_instr(upper(claim_desc), '(^|[^A-Z])WATER', 1, 1)
                  +regexp_instr(upper(claim_desc), '(^|[^A-Z])WTR', 1, 1)
                  + instr(upper(claim_desc), 'FLOOD', 1, 1)
                  + instr(upper(claim_desc), 'FROZE', 1, 1)
                  + regexp_instr(upper(claim_desc), '(^|[^A-Z])ICE ', 1, 1) >0)
                or regexp_instr(upper(claim_desc), '(^|[^A-Z])SNOW', 1, 1)
                  + regexp_instr(upper(claim_desc), '(^|[^A-Z])ICE DAMAGE')> 0
                and (col.water_flag > 0 or (col.structure_flag>0 and (regexp_instr(replace(upper(claim_desc), 'NO WATER DAMAGE','xxx'),'(^|[^A-Z])WATER', 1, 1) +
          regexp_instr(replace(upper(claim_desc), 'NO WTR DAMAGE','xxx'),'(^|[^A-Z])WTR', 1, 1)
          +regexp_instr(replace(upper(claim_desc),'GAS LEAK','xxx'), '(^|[^A-Z])LEAK', 1, 1)>0)))
                )
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
                then 'Water Weather'
          when ((regexp_instr(replace(upper(claim_desc),'GAS LEAK','xxx'), '(^|[^A-Z])LEAK', 1, 1) = 0 and regexp_instr(upper(claim_desc), '(^|[^A-Z])WATER' , 1, 1) = 0
                and (regexp_instr(replace(upper(claim_desc), 'WINDOW', 'xxx'), '(^|[^A-Z])WIND', 1, 1) 
                +instr(upper(claim_desc), 'STORM' , 1, 1)  > 0))
                or instr(upper(claim_desc), 'TORNADO', 1, 1) >0 
                or ((regexp_instr(replace(upper(claim_desc),'BLEW UP','xxx'),'(^|[^A-Z])BLEW' , 1, 1) + 
                 regexp_instr(replace(upper(claim_desc),'BLOW UP','xxx'),'(^|[^A-Z])BLOW' , 1, 1) + 
                 regexp_instr(upper(claim_desc), '(^|[^A-Z])FLEW' , 1, 1) + 
                 regexp_instr(upper(claim_desc), '(^|[^A-Z])BLOWN' , 1, 1) + 
                 regexp_instr(upper(claim_desc), '(^|[^A-Z])BLOW DOWN' , 1, 1) + 
                 --instr(upper(claim_desc), ' FENC' , 1, 1) + 
                 regexp_instr(upper(claim_desc), '(^|[^A-Z])ROOF' , 1, 1) + 
                 instr(upper(claim_desc), 'TREE' , 1, 1) +
                 instr(upper(claim_desc), 'HURRICANE' , 1, 1) +
                 instr(upper(claim_desc), 'BLIZZARD' , 1, 1) +
                 regexp_instr(upper(claim_desc), '(^|[^A-Z])HAIL' , 1, 1) +
                 instr(upper(claim_desc), 'WEIGHT OF SNOW' , 1, 1) > 0 )
                  and col.storm_flag > 0) 
                or ((--same conditions but check for the word 'storm' this thime instead of storm flag.
                 regexp_instr(replace(upper(claim_desc),'BLEW UP','xxx'),'(^|[^A-Z])BLEW' , 1, 1) + regexp_instr(replace(upper(claim_desc),'BLOW UP','xxx'),'(^|[^A-Z])BLOW' , 1, 1) + instr(upper(claim_desc), 'FLEW' , 1, 1) + instr(upper(claim_desc), 'BLOWN' , 1, 1) + instr(upper(claim_desc), 'BLOW DOWN' , 1, 1) + regexp_instr(upper(claim_desc), '(^|[^A-Z])ROOF' , 1, 1) + instr(upper(claim_desc), 'TREE' , 1, 1) +instr(upper(claim_desc), 'HURRICANE' , 1, 1) +instr(upper(claim_desc), 'BLIZZARD' , 1, 1) +regexp_instr(upper(claim_desc), '(^|[^A-Z])HAIL' , 1, 1) +instr(upper(claim_desc), 'WEIGHT OF SNOW' , 1, 1) > 0 )and instr(upper(claim_desc), 'STORM' , 1, 1) > 0) )
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
                and col.fire_flag=0
                then 'Non-Water Storm'
          when col.liability_flag
               + instr(upper(claim_desc), 'LANDLORD HARASS', 1, 1) > 0 
                    and instr(replace(replace(replace(replace(replace(replace(upper(claim_desc),'FIRE HYDRANT', 'xxx'), 'FIRE HAZARD', 'xxx'), 
                    'FIREARM', 'xxx'), 'FIRE PLACE', 'xxx'),'FIREPLACE', 'xxx'), '** NOT A FIRE LOSS **', 'xxx'), 'FIRE', 1, 1) <1 --there are many cases where cause of loss = property damage but claim is actuaaly caused by fire. 
         and col.fire_flag = 0
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
                then 'Liability'
          when regexp_instr(replace(upper(claim_desc),'GAS LEAK','xxx'), '(^|[^A-Z])LEAK', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])BURST', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])BROKE', 1, 1)
              + instr(upper(claim_desc), 'BREAK', 1, 1)
              + instr(upper(claim_desc), 'RUPTURED', 1, 1)
              + instr(upper(claim_desc), 'SPRINKLER BROKE', 1, 1)
              + instr(upper(claim_desc), 'SPRINKLERS BROKE', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])BREAK', 1, 1)> 0
                and (col.water_flag > 0 or (col.structure_flag>0 and (regexp_instr(replace(upper(claim_desc), 'NO WATER DAMAGE','xxx'),'(^|[^A-Z])WATER', 1, 1) +
          regexp_instr(replace(upper(claim_desc), 'NO WTR DAMAGE','xxx'),'(^|[^A-Z])WTR', 1, 1)
          +regexp_instr(replace(upper(claim_desc),'GAS LEAK','xxx'), '(^|[^A-Z])LEAK', 1, 1)
          +regexp_instr(upper(claim_desc), '(^|[^A-Z])PIPE', 1, 1)>0)))
                --and (dh.policy_form is null or dh.policy_form <> 4)-- We offer leak burst in form 4.
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
                then 'Leak/Burst'
          when ((col.water_flag > 0 or (col.structure_flag>0 and (regexp_instr(replace(upper(claim_desc), 'NO WATER DAMAGE','xxx'),'(^|[^A-Z])WATER', 1, 1) +
          regexp_instr(replace(upper(claim_desc), 'NO WTR DAMAGE','xxx'),'(^|[^A-Z])WTR', 1, 1)
          +regexp_instr(replace(upper(claim_desc),'GAS LEAK','xxx'), '(^|[^A-Z])LEAK', 1, 1)>0))) or
              + instr(upper(claim_desc), 'MOISTURE', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])MOLD', 1, 1) > 0 )
         and abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
                then 'Water NW'
          when (ct.coverage_type = 'Identity Fraud' or
               col.theftvand_flag 
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANT MOVED OUT', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])THEFT', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANTS MOVED OUT', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANT SKIPPED OUT', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANTS CAUSED DAMAGE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANT DESTROY', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANTS DESTROY', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANT BROKE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])EVICT', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANTS REMOVED', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANT CAUSED DAMAGE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANTS DAMAGE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANT DAMAGE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])BROKEN INTO', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANTS RUIN', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])TENANT CUT', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])VANDALISM', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])VANDALIZED', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])MARIJUANA', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])UNKNOWN PERSON', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])UNKNOWN INDIVIDUAL', 1, 1)
                + instr(replace(upper(claim_desc),'PIPE BROKE IN','xxx'), 'BROKE IN', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])HEARING AID', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])SCHED', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])SKUNK', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])MOTORIST', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])HIT AND RUN', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])VEHICLE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])POLICE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])NECKLACE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])MISSING', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])CAMERA', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])BROKEN INTO', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])BURGLAR', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])STOLE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])SUSPECT BROKE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])SOMEBODY HIT', 1, 1)
                --+ regexp_instr(upper(claim_desc), '(^|[^A-Z])ITEM', 1, 1)i.e.Leak In Bathroom Damaged Items claim=19749
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])GOLD', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])VEH ROLLED', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])ANIMAL', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])OPOSSUM', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])DEER', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])RODENT', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])BATS', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])BEEHIVE', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])METH LAB', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])RUN OVER', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])VANDAL', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])EARRING', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])RING', 1, 1) --decided to include althoguh contraversial descriptions i.e. Diamond Fell Out Of Ring,Lost Stone Out Of Weeding Ring
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])JEWELRY', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])WATCH', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])LOST', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])EGG', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])BASEBALL', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])BB GUN', 1, 1) 
                -- + instr(upper(claim_desc), ' GOLF BALL', 1, 1) --Many cases like:'A golf ball hit insured`s roof and displaced tiles.' Most of them doesn't indicate intention for the damage.
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])GRAFFITI', 1, 1)
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])STOLE', 1, 1)> 0)
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0 --don't exclude fire_flag = 1 cases. i.e."Home Burglarized/Fire Set", "House Vandelized After Fire" cause_of_loss is selected as fire in these claims.
               and col.FIRE_FLAG=0
                then 'Theft/Vandalism'
           when col.fire_flag + instr(replace(replace(replace(replace(replace(replace(replace(replace(upper(claim_desc),'FIRE SPRINKLER', 'xxx'),'FIRE LINE', 'xxx'),'FIRE HYDRANT', 'xxx'), 'FIRE HAZARD', 'xxx'), 'FIREARM', 'xxx'), 'FIRE PLACE', 'xxx'),'FIREPLACE', 'xxx'), '** NOT A FIRE LOSS **', 'xxx'), 'FIRE', 1, 1) 
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])BURNED', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])BURNING', 1, 1)
               + regexp_instr(upper(claim_desc), '(^|[^A-Z])SMOKE', 1, 1) > 0
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
                then 'Fire'
          when col.storm_flag
                + regexp_instr(upper(claim_desc), '(^|[^A-Z])STORM', 1, 1) > 0
                and col.FIRE_FLAG = 0
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
               then 'Non-Water Storm'
          when (col.breakdown_flag
              + instr(upper(claim_desc), 'WATER HEAT' , 1, 1)
              + instr(upper(claim_desc), 'DISHWA' , 1, 1)
              + instr(upper(claim_desc), 'DISH WASHER' , 1, 1)
              + instr(upper(claim_desc), 'WASHING MACHINE' , 1, 1)
              + instr(upper(claim_desc), 'MALFUN' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])A/C' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])BREAKDOWN' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])AIR CONDITION' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])AC([^A-Z]|$)' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])FRIDGE' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])FRIGE' , 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])SUMP PUMP', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])SHORTED', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])COMPRESSOR', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])FREEZER BROKE DOWN', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])REFRIG BROKE DOWN', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])REFRIGERATOR BROKE DOWN', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])APPLIANCE', 1, 1)
              + regexp_instr(upper(claim_desc), '(^|[^A-Z])BROKE', 1, 1)
              + nvl(cwlf.breakdown,0)
               > 0
                or (regexp_instr(upper(claim_desc), '(^|[^A-Z])SURGE', 1, 1)
                 + regexp_instr(upper(claim_desc), '(^|[^A-Z])OUTAGE', 1, 1)
                 + regexp_instr(upper(claim_desc), '(^|[^A-Z])WIRING', 1, 1)
                 + regexp_instr(upper(claim_desc), '(^|[^A-Z])CIRCUIT', 1, 1)>0))and col.theftvand_flag = 0 and col.FIRE_FLAG=0 and col.FIRE_FLAG=0
         and  abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
               then 'Breakdown'
          else 'Other' end ISO_PERIL,
          dl.cause_group,
          dl.cause_of_loss,
          cl.claim_desc,
          cl.LOSS_CAUSE_CC_ONLY,
          ct.coverage_type,
          cwlf.breakdown,
          cwlf.backup,
          col.fire_flag,
          col.water_flag,
          col.structure_flag,
          col.breakdown_flag,
          col.theft_flag,
          col.theftvand_flag,
          col.storm_flag,
          col.liability_flag,
          col.PURE_LIABILITY_FLAG,
          decode(coalesce(ddf.DIC_APPLIED,'0'),'C',1,0) DIC_FLAG
from clmuser.claim_info cl
    cross join params p  -- uses the fixed 31-Dec-2025 11:59:59 PM valuation date from the params CTE
    join dec_policy@echo.world dp on cl.dec_policy = dp.dec_policy
    join agency@echo.world a on dp.agency_code = a.agency_code
    join dw_claimant_detail@echo.world dl on dl.claim_key = cl.claim and dl.source = cl.source
    join dw_claimant@echo.world dc on dl.claimant_key = dc.claimant_key and dl.source = dc.source
    join resolved_dwelling_fire_unit rdfu
        on cl.source = rdfu.source
       and cl.claim_nbr = rdfu.claim_nbr
       and rdfu.resolved_dec_dwelling_fire is not null
    join dec_dwelling_fire@echo.world ddf
        on rdfu.resolved_dec_dwelling_fire = ddf.dec_dwelling_fire
--    join claimant_trans@echo.world ct on dl.claimant_trans = ct.claimant_trans
--    left join catastrophe@echo.world cat on cl.catastrophe = cat.catastrophe -- use cl.catastrophe instead
--    join claimant_coverage@echo.world cc on (cl.claim = cc.claim and dl.claimant_key = cc.claimant and dl.claimant_coverage = cc.claimant_coverage)
    left join ct_coverage ct
        on cl.source = ct.claim_source
       and cl.claim_nbr = ct.claim_number
    join (select claim_key
            ,source
            ,cause_name
            --,max(case when cause_name in ('Fire', 'Explosion') then 1 else 0 end) fire_flag
            --,max(case when cause_name in ('Water', 'Mold PD', '1st P Mold') then 1 else 0 end) water_flag
            --,max(case when cause_name in ('Structure') then 1 else 0 end) structure_flag--we have obvious water related claims that are eliminated bc cause_name=structure. i.e. claim_nbr:65368. I will use Structure in water_flag but remove cases where it says 'No Water Damage'
            --,max(case when cause_name in ('Mechanical Breakdown', 'Electrical Breakdown') then 1 else 0 end) breakdown_flag
            --,max(case when cause_name in ('Burglary', 'Robbery', 'Theft') then 1 else 0 end) theft_flag
            --,max(case when cause_name in ('Burglary', 'Robbery', 'Theft', 'Vandalism, Malicious Mischief') then 1 else 0 end) theftvand_flag
            --,max(case when cause_name = 'Storm' then 1 else 0 end) storm_flag
            --,max(case when cause_name in ('Bodily Injury', 'Medical Payments', 'Personal Injury', 'Property Damage', 'WC -Indemnity', 'Mold BI', 'Mold PI', 'Child Care', 'Environmental', 'WC-Liability', 'Workers Compensation', 'WC-Med', 'Pollution', 'Habitability') then 1 else 0 end) liability_flag
            --,max(case when cause_name in ('Bodily Injury', 'Personal Injury', 'Property Damage', 'WC -Indemnity', 'Mold BI', 'Mold PI', 'Child Care', 'Environmental', 'WC-Liability','WC -Liability', 'Workers Compensation', 'WC-Med', 'Pollution', 'Habitability') then 1 else 0 end) pure_liability_flag
            ,case when cause_name in ('Fire', 'Explosion') then 1 else 0 end fire_flag
            ,case when cause_name in ('Water', 'Mold PD', '1st P Mold') then 1 else 0 end water_flag
            ,case when cause_name in ('Structure') then 1 else 0 end structure_flag--we have obvious water related claims that are eliminated bc cause_name=structure. i.e. claim_nbr:65368. I will use Structure in water_flag but remove cases where it says 'No Water Damage'
            ,case when cause_name in ('Mechanical Breakdown', 'Electrical Breakdown') then 1 else 0 end breakdown_flag
            ,case when cause_name in ('Burglary', 'Robbery', 'Theft') then 1 else 0 end theft_flag
            ,case when cause_name in ('Burglary', 'Robbery', 'Theft', 'Vandalism, Malicious Mischief') then 1 else 0 end theftvand_flag
            ,case when cause_name = 'Storm' then 1 else 0 end storm_flag
            ,case when cause_name in ('Bodily Injury', 'Medical Payments', 'Personal Injury', 'Property Damage', 'WC -Indemnity', 'Mold BI', 'Mold PI', 'Child Care', 'Environmental', 'WC-Liability', 'WC -Liability','Workers Compensation', 'WC-Med', 'Pollution', 'Habitability') then 1 else 0 end liability_flag
            ,case when cause_name in ('Bodily Injury', 'Personal Injury', 'Property Damage', 'WC -Indemnity', 'Mold BI', 'Mold PI', 'Child Care', 'Environmental', 'WC-Liability','WC -Liability', 'Workers Compensation', 'WC-Med', 'Pollution', 'Habitability') then 1 else 0 end pure_liability_flag
           from 
              (select claim_key, cause_of_loss cause_name, source
              from dw_claimant_detail@echo.world
              where business_line_name in ('Homeowner', 'Dwelling Fire')		
              group by claim_key, cause_of_loss,source	
              --having(sum(nvl(LOSS_PAID,0) + nvl(loss_reserve,0)) > 0)
              )
             group by claim_key, cause_name,source) col on (cl.claim = col.claim_key and col.source = cl.source and col.cause_name=dl.cause_of_loss)
      left join (select cl.claim
             ,max(case when cwlf.water_losstype in ('Water Heater/HVAC','Appliance') then 1 else 0 end) breakdown
             ,max(case when cwlf.water_losstype in ('Backup/Overflow', 'Tree Roots') then 1 else 0 end) backup
             from clmuser.claim_info cl
             join claimant_coverage@echo.world cc on (cl.claim = cc.claim) --this inner join causes no Claims Center (CC) data to be included
             left join cms_col_waterloss_detail@echo.world ccwd
                on (ccwd.claimant_coverage = cc.claimant_coverage)
             left join cms_water_loss_factor@echo.world cwlf
                on (ccwd.cms_water_loss_factor = cwlf.cms_water_loss_factor)
             group by cl.claim
             ) cwlf on cl.claim = cwlf.claim and cl.source = 'CMS'  --NO CC data will be included - this will break logic for some peril mappings but data will still flow through
where 
--  ct.CREATE_ID not in (select baupost_id from ACTUARIAL.BAUPOST_ID) and -- exclude Baupost Subrogation Paid out - AC: removed 6/19/23
  dl.business_line_name = 'Dwelling Fire'
  and dl.a_s_line_nbr in (1, 2.1, 17.1)  --Boiler & Machinery, Cyber Liability/Other Liability Claims Made not included
  --and cl.table_name = 'DEC_DWELLING_FIRE'
-- Unit assignment is handled above through CLAIM_TRANSACTIONS, with a single-unit policy fallback.
  --and dl.a_s_line_nbr = 1

 -- Replaced the runtime bind variable :EXPERIENCE_PERIOD with p.experience_period from the params CTE above.
    -- p.experience_period is hardcoded as 31-Dec-2025 11:59:59 PM so this pull includes all of 2025 and excludes 2026.
    and (cl.date_of_loss > add_months(p.experience_period,-360) --30 accident years for Cat & Large Loss calcs
        or dl.trans_date > add_months(p.experience_period,-96))   --8 calendar years for loss trend
    and cl.date_of_loss <= p.experience_period --exclude accidents that happen after experience period
    and dl.trans_date <= p.experience_period   --exclude transactions that happen after experience period
having abs(sum(dl.loss_paid)) + abs(sum(dl.alloc_expense_paid)) + abs(sum(dl.unalloc_expense_paid)) +
       abs(sum(dl.loss_reserve)) + abs(sum(dl.alloc_expense_reserve)) + abs(sum(dl.unalloc_expense_reserve)) <> 0
group by
       extract(year from dl.trans_date),
       extract(year from cl.date_of_loss),
       cl.date_of_loss,
       case when extract(month from dl.trans_date) in (1,2,3) then to_date('31-Mar-'||extract(year from dl.trans_date),'dd-mon-yyyy')
            when extract(month from dl.trans_date) in (4,5,6) then to_date('30-Jun-'||extract(year from dl.trans_date),'dd-mon-yyyy')
            when extract(month from dl.trans_date) in (7,8,9) then to_date('30-Sep-'||extract(year from dl.trans_date),'dd-mon-yyyy')
            else to_date('31-Dec-'||extract(year from dl.trans_date),'dd-mon-yyyy') end,
       case when extract(month from cl.first_modified) in (1,2,3) then to_date('31-Mar-'||extract(year from cl.first_modified),'dd-mon-yyyy')
            when extract(month from cl.first_modified) in (4,5,6) then to_date('30-Jun-'||extract(year from cl.first_modified),'dd-mon-yyyy')
            when extract(month from cl.first_modified) in (7,8,9) then to_date('30-Sep-'||extract(year from cl.first_modified),'dd-mon-yyyy')
            else to_date('31-Dec-'||extract(year from cl.first_modified),'dd-mon-yyyy') end,
       case when cl.claim_status = 'Closed' then
         case when extract(month from cl.claim_status_date) in (1,2,3) then to_date('31-Mar-'||extract(year from cl.claim_status_date),'dd-mon-yyyy')
              when extract(month from cl.claim_status_date) in (4,5,6) then to_date('30-Jun-'||extract(year from cl.claim_status_date),'dd-mon-yyyy')
              when extract(month from cl.claim_status_date) in (7,8,9) then to_date('30-Sep-'||extract(year from cl.claim_status_date),'dd-mon-yyyy')
              else to_date('31-Dec-'||extract(year from cl.claim_status_date),'dd-mon-yyyy') end
         else null end,
       cl.POLICY_SEARCH_NBR,
       rdfu.claim_key,
       rdfu.building_key,
       rdfu.unit_match_method,
       cl.EFFECTIVE_DATE,
       dp.agency_code,
       dp.agency_name,
       a.domicile_state,
       dc.writing_company,
       case when dp.agency_code in (24949,26906,26907,26908,26910,26911,26914,
              26916,26917,26919,26922,26924,26946,26947,26949,26951,26961,27250,27251,27252,27901,27902,27903,
              27904,27905,27906,27908,27909,27911,27913,27916,27917,27918,27919,27922,27923,27924,27925,27945,
              27946,27947,27959,27961,47141,47179,47212,47222,47225,47247,49951,50018,50022,50023,50024,50025,
              50035,50038,50039,50042,50043,50046,50048,50049,50051,50053,50054,50056,50105,50147,50161,50950,
              50951,50952,71000,71001,71002,71005,71006,71008,71009,71010,71011,71012,71013,71015,71016,71017,
              71018,71019,71020,71021,71022,71023,71024,71025,71025,71026,71027,71028,71029,71030,71031,71032,
              71033,71034,71035,71036,71037,71038,71039,71040,71041,71042,71044,71045,71046,71047,71048,71049,
              71050,71051,71052,71053,71054,71055,71056,71057,71058,71059,71060,71061,71062,71063,71070,71071,71072,71073) then 'Washington Branch'
            when dp.agency_code in (48060, 26700,26722,27710,47470,47471,55001,66180,66181,66182,66183,66410,66420,71504) then 'Alternative Markets Programs' else dp.branch_name end,
       dp.branch_nbr,
       dp.business_line,
       dl.a_s_line_nbr,
       dl.a_s_line_desc,
       dl.line_nbr,
       dl.coverage_line_desc,
       ddf.policy_form,
       dl.dept_nbr,
       dl.dept_desc,
       dc.claim_nbr,
       cl.claim,
       cl.claim_status,
       cl.claim_status_date,
       dl.cause_of_loss, 
       cwlf.breakdown
        ,cwlf.backup
        ,col.fire_flag
        ,col.water_flag
        ,col.breakdown_flag
        ,col.theft_flag
        ,col.pure_liability_flag
        ,col.theftvand_flag
        ,col.storm_flag
        ,col.liability_flag,
       cl.claim_desc,
       decode(cl.catastrophe,null,'No','Yes'),
       ddf.dwelling_limit,
       ddf.contents_limit,
       dl.cause_group,          
       cl.LOSS_CAUSE_CC_ONLY,
       ct.coverage_type,
       col.structure_flag,
       decode(coalesce(ddf.DIC_APPLIED,'0'),'C',1,0)
;
