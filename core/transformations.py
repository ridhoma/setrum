MODELS = [
    {
        "table_name": "analytics_fct_consumptions_half_hourly",
        "query": """
            SELECT
                ea.account_number
                , ea.account_id
                , c.mpan
                , c.meter_serial_number
                , ea.tariff_code
                , c.interval_start as interval_start_at_utc
                , c.interval_end as interval_end_at_utc
                , (unixepoch(c.interval_end) - unixepoch(c.interval_start))*1.0/60 as interval_minutes
                , price.value_exc_vat as price_pence_exc_vat
                , price.value_inc_vat as price_pence_inc_vat
                , c.consumption_kwh
                , c.consumption_kwh * price.value_exc_vat as consumption_pence_exc_vat
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
                , standing_charges.value_exc_vat as standing_charge_pence_exc_vat
                , standing_charges.value_inc_vat as standing_charge_pence_inc_vat
                , dc.consumption_pence_exc_vat + standing_charges.value_exc_vat as total_pence_exc_vat
                , dc.consumption_pence_inc_vat + standing_charges.value_inc_vat as total_pence_inc_vat
                , (dc.consumption_pence_inc_vat - dc.consumption_pence_exc_vat) 
                    + (standing_charges.value_inc_vat - standing_charges.value_exc_vat) as total_pence_vat
            FROM daily_consumption as dc
            LEFT JOIN source_electricity_standing_charges as standing_charges
                ON dc.tariff_code = standing_charges.tariff_code
                AND dc.interval_start >= standing_charges.interval_start
                AND dc.interval_start <= standing_charges.interval_end
        """
    }
]
