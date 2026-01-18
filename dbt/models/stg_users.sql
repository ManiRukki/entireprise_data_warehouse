
-- staging/stg_users.sql
with source as (
    select * from {{ source('raw', 'users') }}
),

renamed as (
    select
        id as user_id,
        name as full_name,
        email,
        created_at
    from source
)

select * from renamed
