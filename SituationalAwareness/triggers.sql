-- Set up and trigger from the vessel table

DROP TABLE IF EXISTS ship;

CREATE TABLE IF NOT EXISTS ship (
	id TEXT,
	t TIMESTAMP WITH TIME ZONE,
	lat DOUBLE PRECISION NOT NULL,
	lon DOUBLE PRECISION NOT NULL,
	PRIMARY KEY(t, id)
	); -- ship

DROP FUNCTION IF EXISTS ship_updated_func CASCADE;
DROP TRIGGER IF EXISTS ship_updated ON ship CASCADE;

CREATE OR REPLACE FUNCTION ship_updated_func()
  RETURNS  TRIGGER AS $psql$
BEGIN
  PERFORM pg_notify('ship_updated', 'ship');
  RETURN NEW;
end;
$psql$ 
LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER ship_updated AFTER INSERT OR UPDATE ON ship
  FOR EACH STATEMENT
    EXECUTE PROCEDURE ship_updated_func('ship_updated', 'ship');

-- Triggers for drifter table

DROP FUNCTION IF EXISTS drifter_updated_func CASCADE;
DROP TRIGGER IF EXISTS drifter_updated ON drifter CASCADE;

CREATE OR REPLACE FUNCTION drifter_updated_func() 
  RETURNS  TRIGGER AS $psql$
BEGIN
  PERFORM pg_notify('drifter_updated', 'drifter');
  RETURN NEW;
end;
$psql$ 
LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER drifter_updated AFTER INSERT OR UPDATE 
  ON drifter
  FOR EACH STATEMENT
    EXECUTE PROCEDURE drifter_updated_func();
