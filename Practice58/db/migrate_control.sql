BEGIN;

-- 1) Контроль часу ПУ (астрономічний + оперативний)
CREATE TABLE IF NOT EXISTS time_control (
  id           INT PRIMARY KEY DEFAULT 1,
  astro_time   TIMESTAMP NOT NULL DEFAULT now(),
  op_date      DATE NOT NULL,
  op_day_start TIME NOT NULL DEFAULT '06:00',
  mode         TEXT NOT NULL CHECK (mode IN ('auto','manual')),
  updated_at   TIMESTAMP NOT NULL DEFAULT now()
);

-- один активний рядок
INSERT INTO time_control (id, astro_time, op_date, op_day_start, mode)
SELECT 1, now(), CURRENT_DATE, '06:00', 'manual'
WHERE NOT EXISTS (SELECT 1 FROM time_control WHERE id=1);


-- 2) Регламент (контрольні точки)
CREATE TABLE IF NOT EXISTS doc_schedule (
  schedule_id     BIGSERIAL PRIMARY KEY,
  doc_type_code   TEXT NOT NULL,      -- 'БД','ПБД','БЧС','ІБ','ПзБД'
  due_time        TIME NULL,          -- 12:30, 17:30, 17:00; NULL для подієвого
  tolerance_min   INT  NOT NULL DEFAULT 10,
  is_event_driven BOOLEAN NOT NULL DEFAULT FALSE,
  event_type      TEXT NULL,          -- наприклад 'RIZKA_ZMINA'
  sla_minutes     INT  NULL,          -- для подієвого (ПзБД)
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  note            TEXT NULL
);

-- унікальність фіксованих: (doc_type_code, due_time) коли is_event_driven = false
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public' AND indexname = 'uq_doc_schedule_fixed_idx'
  ) THEN
    CREATE UNIQUE INDEX uq_doc_schedule_fixed_idx
    ON doc_schedule (doc_type_code, due_time)
    WHERE is_event_driven = FALSE;
  END IF;
END $$;

-- унікальність подієвих: (doc_type_code, event_type) коли is_event_driven = true
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public' AND indexname = 'uq_doc_schedule_event_idx'
  ) THEN
    CREATE UNIQUE INDEX uq_doc_schedule_event_idx
    ON doc_schedule (doc_type_code, event_type)
    WHERE is_event_driven = TRUE;
  END IF;
END $$;


-- 3) Події (для ПзБД)
CREATE TABLE IF NOT EXISTS events (
  event_id    BIGSERIAL PRIMARY KEY,
  event_time  TIMESTAMP NOT NULL,
  op_date     DATE NOT NULL,
  event_type  TEXT NOT NULL,          -- 'RIZKA_ZMINA'
  sector_id   INT NULL,
  severity    INT NULL,
  note        TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_op_date ON events(op_date);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type, event_time DESC);


-- 4) Заповнення регламенту (без ON CONSTRAINT — через WHERE NOT EXISTS)

-- БД 12:30
INSERT INTO doc_schedule (doc_type_code, due_time, tolerance_min, is_event_driven, note)
SELECT 'БД', '12:30', 10, FALSE, 'БД має бути відпрацьовано до 12:30'
WHERE NOT EXISTS (
  SELECT 1 FROM doc_schedule
  WHERE doc_type_code='БД' AND due_time='12:30' AND is_event_driven=FALSE
);

-- БД 17:30
INSERT INTO doc_schedule (doc_type_code, due_time, tolerance_min, is_event_driven, note)
SELECT 'БД', '17:30', 10, FALSE, 'БД має бути відпрацьовано до 17:30'
WHERE NOT EXISTS (
  SELECT 1 FROM doc_schedule
  WHERE doc_type_code='БД' AND due_time='17:30' AND is_event_driven=FALSE
);

-- ПБД 17:30
INSERT INTO doc_schedule (doc_type_code, due_time, tolerance_min, is_event_driven, note)
SELECT 'ПБД', '17:30', 10, FALSE, 'ПБД має бути відпрацьовано до 17:30'
WHERE NOT EXISTS (
  SELECT 1 FROM doc_schedule
  WHERE doc_type_code='ПБД' AND due_time='17:30' AND is_event_driven=FALSE
);

-- БЧС 17:30
INSERT INTO doc_schedule (doc_type_code, due_time, tolerance_min, is_event_driven, note)
SELECT 'БЧС', '17:30', 10, FALSE, 'БЧС має бути відпрацьовано до 17:30'
WHERE NOT EXISTS (
  SELECT 1 FROM doc_schedule
  WHERE doc_type_code='БЧС' AND due_time='17:30' AND is_event_driven=FALSE
);

-- ІБ 17:00
INSERT INTO doc_schedule (doc_type_code, due_time, tolerance_min, is_event_driven, note)
SELECT 'ІБ', '17:00', 10, FALSE, 'ІБ станом на 17:00'
WHERE NOT EXISTS (
  SELECT 1 FROM doc_schedule
  WHERE doc_type_code='ІБ' AND due_time='17:00' AND is_event_driven=FALSE
);

-- ПзБД (подієво)
INSERT INTO doc_schedule (doc_type_code, due_time, tolerance_min, is_event_driven, event_type, sla_minutes, note)
SELECT 'ПзБД', NULL, 0, TRUE, 'RIZKA_ZMINA', 60, 'ПзБД при різкій зміні обстановки (SLA 60 хв)'
WHERE NOT EXISTS (
  SELECT 1 FROM doc_schedule
  WHERE doc_type_code='ПзБД' AND is_event_driven=TRUE AND event_type='RIZKA_ZMINA'
);

COMMIT;
