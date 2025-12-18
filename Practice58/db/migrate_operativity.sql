-- db/migrate_operativity.sql
CREATE TABLE IF NOT EXISTS norms (
  norm_id SERIAL PRIMARY KEY,
  doc_type_id INT NOT NULL REFERENCES doc_types(doc_type_id),
  priority INT NOT NULL CHECK (priority IN (1,2,3)),
  max_minutes INT NOT NULL
);

-- приклад нормативів
INSERT INTO norms (doc_type_id, priority, max_minutes)
SELECT dt.doc_type_id, v.priority, v.max_minutes
FROM doc_types dt
JOIN (VALUES
  (1, 60),   -- priority=1, 60 хв
  (2, 180),  -- priority=2, 180 хв
  (3, 360)   -- priority=3, 360 хв
) v(priority, max_minutes) ON TRUE
WHERE dt.code IN ('ПБД','БД','БЧС','ЗВІТ','РОЗП')
ON CONFLICT DO NOTHING;
