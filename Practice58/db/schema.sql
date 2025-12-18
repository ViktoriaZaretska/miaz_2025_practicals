-- СХЕМА БД (сумісна): без GENERATED, cycle_minutes рахує тригер
-- Працює для shtab_insait

DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS norms CASCADE;
DROP TABLE IF EXISTS units CASCADE;
DROP TABLE IF EXISTS sectors CASCADE;
DROP TABLE IF EXISTS doc_types CASCADE;

CREATE TABLE units (
  unit_id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,      -- J1, J2, J3...
  name TEXT NOT NULL
);

CREATE TABLE sectors (
  sector_id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE doc_types (
  doc_type_id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,      -- ПБД, БД, БЧС, ЗВІТ, РОЗП
  name TEXT NOT NULL
);

CREATE TABLE documents (
  doc_id BIGSERIAL PRIMARY KEY,

  reg_number TEXT,
  title TEXT NOT NULL,
  doc_date TIMESTAMP NOT NULL,

  unit_id INT NOT NULL REFERENCES units(unit_id),
  sector_id INT REFERENCES sectors(sector_id),
  doc_type_id INT NOT NULL REFERENCES doc_types(doc_type_id),

  status TEXT NOT NULL CHECK (status IN ('отримано','в_роботі','доведено','прострочено')),
  priority INT NOT NULL DEFAULT 2 CHECK (priority IN (1,2,3)), -- 1 = терміново

  received_at TIMESTAMP NOT NULL,
  processed_at TIMESTAMP,
  delivered_at TIMESTAMP,

  cycle_minutes INT
);

CREATE TABLE norms (
  norm_id SERIAL PRIMARY KEY,
  doc_type_id INT NOT NULL REFERENCES doc_types(doc_type_id),
  priority INT NOT NULL CHECK (priority IN (1,2,3)),
  max_minutes INT NOT NULL,
  UNIQUE (doc_type_id, priority)
);

-- Функція + тригер: автоматично рахує cycle_minutes
CREATE OR REPLACE FUNCTION trg_set_cycle_minutes()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.received_at IS NULL THEN
    NEW.cycle_minutes := NULL;
    RETURN NEW;
  END IF;

  IF NEW.delivered_at IS NOT NULL THEN
    NEW.cycle_minutes := (EXTRACT(EPOCH FROM (NEW.delivered_at - NEW.received_at)) / 60)::INT;
  ELSIF NEW.processed_at IS NOT NULL THEN
    NEW.cycle_minutes := (EXTRACT(EPOCH FROM (NEW.processed_at - NEW.received_at)) / 60)::INT;
  ELSE
    NEW.cycle_minutes := NULL;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_cycle_minutes ON documents;

CREATE TRIGGER set_cycle_minutes
BEFORE INSERT OR UPDATE OF received_at, processed_at, delivered_at
ON documents
FOR EACH ROW
EXECUTE FUNCTION trg_set_cycle_minutes();

-- Індекси для швидких фільтрів дашборду
CREATE INDEX IF NOT EXISTS idx_documents_doc_date ON documents(doc_date);
CREATE INDEX IF NOT EXISTS idx_documents_unit ON documents(unit_id);
CREATE INDEX IF NOT EXISTS idx_documents_sector ON documents(sector_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_priority ON documents(priority);
