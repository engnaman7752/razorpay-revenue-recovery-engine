-- Run once against your local Postgres, e.g.
--   psql -U postgres -f scripts/create-db.sql
-- Flyway creates all TABLES on first backend boot; it does not create the
-- DATABASE itself, which is what this file is for.
CREATE DATABASE recovery;
