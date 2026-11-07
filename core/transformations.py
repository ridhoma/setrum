MODELS = [
    {
        "table_name": "analytics_fct_consumptions_half_hourly",
        "query": """
            -- =========================================================================
            -- Half-Hourly Consumption Analytics Mart
            --
            -- UK Domestic Electricity VAT Logic:
            -- 1. Standard Reduced Rate (5% VAT): Section 29A & Schedule 7A, Group 1 of
            --    the Value Added Tax Act 1994 for domestic fuel and power.
            -- 2. Temporary Zero-Rate Measure (0% VAT): In Great Britain, domestic
            --    electricity is temporarily zero-rated from 2026-10-01 to 2027-06-30
            --    (The Value Added Tax (Domestic Electricity) (Zero-Rating) Order 2026,
            --    extended through 30 June 2027).
            -- 3. Octopus Energy API Rate Handling:
            --    - During 0% VAT (2026-10-01 to 2027-06-30): value_exc_vat == value_inc_vat
            --      is genuinely accurate because 0% VAT applies.
            --    - Outside 0% VAT (< 2026-10-01 or > 2027-06-30): Octopus often entered
            --      the consumer gross price (inc. 5% VAT) into both value_exc_vat and
            --      value_inc_vat for fixed tariffs. If they match outside the zero-rate
            --      window, we derive the net rate as value_inc_vat / 1.05.
            -- =========================================================================
            SELECT
                ea.account_number
                , ea.account_id
                , c.mpan
                , c.meter_serial_number
                , ea.tariff_code
                , c.interval_start as interval_start_at_utc
                , c.interval_end as interval_end_at_utc
                , (unixepoch(c.interval_end) - unixepoch(c.interval_start))*1.0/60 as interval_minutes
                , CASE 
                    -- Temporary 0% VAT window for GB domestic electricity
                    WHEN date(c.interval_start) >= '2026-10-01' AND date(c.interval_start) <= '2027-06-30'
                    THEN price.value_inc_vat
                    -- Outside zero-rate window: 5% VAT. If Octopus returned equal gross rates, derive net.
                    WHEN abs(price.value_inc_vat - price.value_exc_vat) < 0.0001 
                    THEN price.value_inc_vat / 1.05 
                    ELSE price.value_exc_vat 
                  END as price_pence_exc_vat
                , price.value_inc_vat as price_pence_inc_vat
                , c.consumption_kwh
                , c.consumption_kwh * (CASE 
                    WHEN date(c.interval_start) >= '2026-10-01' AND date(c.interval_start) <= '2027-06-30'
                    THEN price.value_inc_vat
                    WHEN abs(price.value_inc_vat - price.value_exc_vat) < 0.0001 
                    THEN price.value_inc_vat / 1.05 
                    ELSE price.value_exc_vat 
                  END) as consumption_pence_exc_vat
                , c.consumption_kwh * price.value_inc_vat as consumption_pence_inc_vat
            FROM source_consumptions as c
            INNER JOIN source_electricity_agreements as ea
                ON ea.mpan = c.mpan
                   AND c.interval_start >= ea.valid_from
                   AND (c.interval_start < ea.valid_to OR ea.valid_to IS NULL)
            INNER JOIN source_electricity_standard_unit_rates as price
                ON price.tariff_code = ea.tariff_code
                   AND c.interval_start >= price.interval_start
                   AND c.interval_start < price.interval_end
            ORDER BY c.interval_start desc;
        """
    },
    {
        "table_name": "analytics_fct_consumptions_daily",
        "query": """
            -- =========================================================================
            -- Daily Consumption Analytics Mart
            --
            -- Applies standing charges and computes exc-VAT, inc-VAT, and total VAT.
            -- Follows same UK statutory rules:
            -- - 0% VAT from 2026-10-01 to 2027-06-30 (standing charge VAT is £0.00).
            -- - 5% VAT outside that window (standing charge VAT is inc - (inc / 1.05)).
            -- =========================================================================
            WITH
            daily_consumption as (
                SELECT account_number
                    , account_id
                    , mpan
                    , meter_serial_number
                    , tariff_code
                    , date(interval_start_at_utc) as date
                    , sum(consumption_kwh) as consumption_kwh
                    , sum(consumption_pence_exc_vat) as consumption_pence_exc_vat
                    , sum(consumption_pence_inc_vat) as consumption_pence_inc_vat
                    , min(interval_start_at_utc) as interval_start
                    , max(interval_end_at_utc) as interval_end
                FROM analytics_fct_consumptions_half_hourly
                GROUP BY 1,2,3,4,5,6
            )
            SELECT
                dc.account_number
                , dc.account_id
                , dc.mpan
                , dc.meter_serial_number
                , dc.tariff_code
                , dc.date
                , dc.interval_start
                , dc.interval_end
                , dc.consumption_kwh
                , dc.consumption_pence_exc_vat
                , dc.consumption_pence_inc_vat
                , CASE 
                    WHEN dc.date >= '2026-10-01' AND dc.date <= '2027-06-30'
                    THEN standing_charges.value_inc_vat
                    WHEN abs(standing_charges.value_inc_vat - standing_charges.value_exc_vat) < 0.0001 
                    THEN standing_charges.value_inc_vat / 1.05 
                    ELSE standing_charges.value_exc_vat 
                  END as standing_charge_pence_exc_vat
                , standing_charges.value_inc_vat as standing_charge_pence_inc_vat
                , dc.consumption_pence_exc_vat + (CASE 
                    WHEN dc.date >= '2026-10-01' AND dc.date <= '2027-06-30'
                    THEN standing_charges.value_inc_vat
                    WHEN abs(standing_charges.value_inc_vat - standing_charges.value_exc_vat) < 0.0001 
                    THEN standing_charges.value_inc_vat / 1.05 
                    ELSE standing_charges.value_exc_vat 
                  END) as total_pence_exc_vat
                , dc.consumption_pence_inc_vat + standing_charges.value_inc_vat as total_pence_inc_vat
                , (dc.consumption_pence_inc_vat - dc.consumption_pence_exc_vat) 
                    + (standing_charges.value_inc_vat - (CASE 
                        WHEN dc.date >= '2026-10-01' AND dc.date <= '2027-06-30'
                        THEN standing_charges.value_inc_vat
                        WHEN abs(standing_charges.value_inc_vat - standing_charges.value_exc_vat) < 0.0001 
                        THEN standing_charges.value_inc_vat / 1.05 
                        ELSE standing_charges.value_exc_vat 
                      END)) as total_pence_vat
            FROM daily_consumption as dc
            LEFT JOIN source_electricity_standing_charges as standing_charges
                ON dc.tariff_code = standing_charges.tariff_code
                AND dc.interval_start >= standing_charges.interval_start
                AND dc.interval_start <= standing_charges.interval_end
        """
    }
]
