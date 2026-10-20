select
    geolocation_zip_code_prefix                    as zip_code_prefix,
    geolocation_lat                               as lat,
    geolocation_lng                               as lng,
    trim(geolocation_city)                        as city,
    upper(trim(geolocation_state))                as state
from {{ source('raw', 'geolocation') }}
