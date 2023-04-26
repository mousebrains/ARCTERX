CREATE TABLE IF NOT EXISTS ship ( -- R/V Thompson
  id VARCHAR(20) COMPRESSION lz4,
  t TIMESTAMP WITH TIME ZONE,
  lat DOUBLE PRECISION, -- May be null, but other data should not be
  lon DOUBLE PRECISION,
  sog DOUBLE PRECISION,
  cog DOUBLE PRECISION,
  dilution DOUBLE PRECISION,
  altitude DOUBLE PRECISION,
  height DOUBLE PRECISION,
  qCSV BOOLEAN DEFAULT FALSE,
  PRIMARY KEY(t, id)
);

-- Fast lookup with id
CREATE INDEX IF NOT EXISTS ship_ident ON ship (id);

-- Function sends a notification whenever ship is updated
CREATE OR REPLACE FUNCTION ship_updated_func() 
  RETURNS  TRIGGER AS $psql$
BEGIN
  PERFORM pg_notify('ship_updated', 'ship');
  RETURN NEW;
end;
$psql$ 
LANGUAGE plpgsql;

-- When ship is updated or inserted into, call the nofiication function
CREATE OR REPLACE TRIGGER ship_updated AFTER INSERT OR UPDATE 
  ON ship
  FOR EACH STATEMENT
    EXECUTE PROCEDURE ship_updated_func();

--------

CREATE TABLE IF NOT EXISTS filePosition ( -- Position to start reading records from
  filename TEXT COMPRESSION lz4 PRIMARY KEY,
  position BIGINT
); -- filePosition

