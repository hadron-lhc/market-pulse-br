-- Grain: zip_code_prefix (zip centroids from the raw geolocation observations).
-- The raw table has up to ~1146 rows per zip; joining it directly to any fact
-- would fan out rows, so it is always used through this model (1 row per zip).
select
    zip_code_prefix,
    round(avg(lat), 6)                              as avg_lat,
    round(avg(lng), 6)                              as avg_lng,
    min(city)                                       as city,
    min(state)                                      as state,
    count(*)                                        as observation_count
from {{ ref('stg_geolocation') }}
group by zip_code_prefix
