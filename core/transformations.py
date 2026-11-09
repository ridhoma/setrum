MODELS = [
    {
        "table_name": "analytics_fct_consumptions_half_hourly",
        "query": """
            -- =========================================================================
            -- Half-Hourly Consumption Analytics Mart
            --
            -- UK Domestic Electricity VAT & Timezone Logic:
            -- 1. Great Britain Local Time (Europe/London):
            --    British Summer Time (BST, UTC+1) starts at 01:00 UTC on the last
            --    Sunday of March and ends at 01:00 UTC on the last Sunday of October.
            --    Outside that window, UK time is GMT (UTC+0).
            -- 2. Standard Reduced Rate (5% VAT): Section 29A & Schedule 7A, Group 1 of
            --    the Value Added Tax Act 1994 for domestic fuel and power.
            -- 3. Temporary Zero-Rate Measure (0% VAT): In Great Britain, domestic
            --    electricity is temporarily zero-rated from 2026-10-01 to 2027-06-30
            --    (The Value Added Tax (Domestic Electricity) (Zero-Rating) Order 2026,
            --    extended through 30 June 2027). Evaluated on Europe/London local date
            --    so 2026-09-30T23:00:00Z (00:00 BST on 1 Oct) gets 0% VAT.
            -- 4. Octopus Energy API Rate Handling:
            --    - price.value_exc_vat is ALWAYS the net (exc. VAT) unit rate.
            --    - During 0% VAT (local date 2026-10-01 to 2027-06-30):
            --      price_pence_inc_vat = price.value_exc_vat (0% VAT applies).
            --    - Outside 0% VAT (< 2026-10-01 or > 2027-06-30):
            --      For fixed tariffs spanning into 0% VAT, Octopus API entered the net
            --      rate into both value_exc_vat and value_inc_vat. When they match,
            --      we gross up by 5% (value_exc_vat * 1.05) to get the true inc-VAT price.
            -- =========================================================================
            WITH base AS (
                SELECT
                    ea.account_number
                    , ea.account_id
                    , c.mpan
                    , c.meter_serial_number
                    , ea.tariff_code
                    , c.interval_start as interval_start_at_utc
                    , c.interval_end as interval_end_at_utc
                    , (unixepoch(c.interval_end) - unixepoch(c.interval_start))*1.0/60 as interval_minutes
                    , c.consumption_kwh
                    , price.value_exc_vat as unit_rate_exc_vat
                    , price.value_inc_vat as unit_rate_inc_vat
                    , CASE
                        WHEN c.interval_start >= printf('%s-03-%02dT01:00:00Z', substr(c.interval_start, 1, 4), 31 - CAST(strftime('%w', substr(c.interval_start, 1, 4) || '-03-31') AS INTEGER))
                         AND c.interval_start <  printf('%s-10-%02dT01:00:00Z', substr(c.interval_start, 1, 4), 31 - CAST(strftime('%w', substr(c.interval_start, 1, 4) || '-10-31') AS INTEGER))
                        THEN date(c.interval_start, '+1 hour')
                        ELSE date(c.interval_start)
                      END as local_date
                FROM source_consumptions as c
                INNER JOIN source_electricity_agreements as ea
                    ON ea.mpan = c.mpan
                       AND c.interval_start >= ea.valid_from
                       AND (c.interval_start < ea.valid_to OR ea.valid_to IS NULL)
                INNER JOIN source_electricity_standard_unit_rates as price
                    ON price.tariff_code = ea.tariff_code
                       AND c.interval_start >= price.interval_start
                       AND c.interval_start < price.interval_end
            )
            SELECT
                account_number
                , account_id
                , mpan
                , meter_serial_number
                , tariff_code
                , interval_start_at_utc
                , interval_end_at_utc
                , interval_minutes
                , unit_rate_exc_vat as price_pence_exc_vat
                , CASE 
                    -- Temporary 0% VAT window for GB domestic electricity (UK local date)
                    WHEN local_date >= '2026-10-01' AND local_date <= '2027-06-30'
                    THEN unit_rate_exc_vat
                    -- Outside zero-rate window (standard 5% VAT): if Octopus returned net in both fields, gross up by 5%
                    WHEN abs(unit_rate_inc_vat - unit_rate_exc_vat) < 0.0001 
                    THEN unit_rate_exc_vat * 1.05 
                    ELSE unit_rate_inc_vat 
                  END as price_pence_inc_vat
                , consumption_kwh
                , consumption_kwh * unit_rate_exc_vat as consumption_pence_exc_vat
                , consumption_kwh * (CASE 
                    -- Temporary 0% VAT window for GB domestic electricity (UK local date)
                    WHEN local_date >= '2026-10-01' AND local_date <= '2027-06-30'
                    THEN unit_rate_exc_vat
                    -- Outside zero-rate window (standard 5% VAT): if Octopus returned net in both fields, gross up by 5%
                    WHEN abs(unit_rate_inc_vat - unit_rate_exc_vat) < 0.0001 
                    THEN unit_rate_exc_vat * 1.05 
                    ELSE unit_rate_inc_vat 
                  END) as consumption_pence_inc_vat
            FROM base
            ORDER BY interval_start_at_utc desc;
        """
    },
    {
        "table_name": "analytics_fct_consumptions_daily",
        "query": """
            -- =========================================================================
            -- Daily Consumption Analytics Mart
            --
            -- Applies standing charges and computes exc-VAT, inc-VAT, and total VAT.
            -- Follows UK statutory and Octopus Energy portal rules:
            -- 1. Bucketed by Europe/London local date (date of interval_start_at_utc).
            -- 2. Tariff selection: strictly 1 row per (account_id, mpan, meter_serial_number, date),
            --    using the tariff active at the end/majority of the day to avoid double-charging
            --    standing charges on mid-day tariff switch days.
            -- 3. Standing charges:
            --    - standing_charges.value_exc_vat is ALWAYS the net (exc. VAT) standing charge.
            --    - 0% VAT from 2026-10-01 to 2027-06-30: standing charge inc_vat = exc_vat.
            --    - 5% VAT outside that window: if Octopus returned equal net rates in both
            --      fields, gross up by 5% (value_exc_vat * 1.05) to get inc_vat.
            -- 4. Standing charge join boundary: [interval_start, interval_end) using '<'
            --    so boundary dates (e.g. 2026-01-01T00:00:00Z) are never duplicated.
            -- =========================================================================
            WITH daily_hh AS (
                SELECT
                    account_number
                    , account_id
                    , mpan
                    , meter_serial_number
                    , tariff_code
                    , interval_start_at_utc
                    , interval_end_at_utc
                    , consumption_kwh
                    , consumption_pence_exc_vat
                    , consumption_pence_inc_vat
                    , CASE
                        WHEN interval_start_at_utc >= printf('%s-03-%02dT01:00:00Z', substr(interval_start_at_utc, 1, 4), 31 - CAST(strftime('%w', substr(interval_start_at_utc, 1, 4) || '-03-31') AS INTEGER))
                         AND interval_start_at_utc <  printf('%s-10-%02dT01:00:00Z', substr(interval_start_at_utc, 1, 4), 31 - CAST(strftime('%w', substr(interval_start_at_utc, 1, 4) || '-10-31') AS INTEGER))
                        THEN date(interval_start_at_utc, '+1 hour')
                        ELSE date(interval_start_at_utc)
                      END as date
                FROM analytics_fct_consumptions_half_hourly
            ),
            latest_tariff AS (
                SELECT
                    account_number
                    , account_id
                    , mpan
                    , meter_serial_number
                    , date
                    , tariff_code
                FROM (
                    SELECT
                        account_number
                        , account_id
                        , mpan
                        , meter_serial_number
                        , date
                        , tariff_code
                        , ROW_NUMBER() OVER (
                            PARTITION BY account_number, account_id, mpan, meter_serial_number, date
                            ORDER BY interval_start_at_utc DESC
                        ) as rn
                    FROM daily_hh
                )
                WHERE rn = 1
            ),
            daily_consumption AS (
                SELECT
                    dh.account_number
                    , dh.account_id
                    , dh.mpan
                    , dh.meter_serial_number
                    , lt.tariff_code
                    , dh.date
                    , sum(dh.consumption_kwh) as consumption_kwh
                    , sum(dh.consumption_pence_exc_vat) as consumption_pence_exc_vat
                    , sum(dh.consumption_pence_inc_vat) as consumption_pence_inc_vat
                    , min(dh.interval_start_at_utc) as interval_start
                    , max(dh.interval_end_at_utc) as interval_end
                FROM daily_hh dh
                JOIN latest_tariff lt
                    ON lt.account_number = dh.account_number
                   AND lt.account_id = dh.account_id
                   AND lt.mpan = dh.mpan
                   AND lt.meter_serial_number = dh.meter_serial_number
                   AND lt.date = dh.date
                GROUP BY dh.account_number, dh.account_id, dh.mpan, dh.meter_serial_number, lt.tariff_code, dh.date
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
                , standing_charges.value_exc_vat as standing_charge_pence_exc_vat
                , CASE 
                    WHEN dc.date >= '2026-10-01' AND dc.date <= '2027-06-30'
                    THEN standing_charges.value_exc_vat
                    WHEN abs(standing_charges.value_inc_vat - standing_charges.value_exc_vat) < 0.0001 
                    THEN standing_charges.value_exc_vat * 1.05 
                    ELSE standing_charges.value_inc_vat 
                  END as standing_charge_pence_inc_vat
                , dc.consumption_pence_exc_vat + standing_charges.value_exc_vat as total_pence_exc_vat
                , dc.consumption_pence_inc_vat + (CASE 
                    WHEN dc.date >= '2026-10-01' AND dc.date <= '2027-06-30'
                    THEN standing_charges.value_exc_vat
                    WHEN abs(standing_charges.value_inc_vat - standing_charges.value_exc_vat) < 0.0001 
                    THEN standing_charges.value_exc_vat * 1.05 
                    ELSE standing_charges.value_inc_vat 
                  END) as total_pence_inc_vat
                , (dc.consumption_pence_inc_vat - dc.consumption_pence_exc_vat) 
                    + ((CASE 
                        WHEN dc.date >= '2026-10-01' AND dc.date <= '2027-06-30'
                        THEN standing_charges.value_exc_vat
                        WHEN abs(standing_charges.value_inc_vat - standing_charges.value_exc_vat) < 0.0001 
                        THEN standing_charges.value_exc_vat * 1.05 
                        ELSE standing_charges.value_inc_vat 
                      END) - standing_charges.value_exc_vat) as total_pence_vat
            FROM daily_consumption as dc
            LEFT JOIN source_electricity_standing_charges as standing_charges
                ON dc.tariff_code = standing_charges.tariff_code
                AND dc.interval_start >= standing_charges.interval_start
                AND (dc.interval_start < standing_charges.interval_end OR standing_charges.interval_end IS NULL)
        """
    }
]
