DROP TABLE IF EXISTS public.resource_allocations;

CREATE TABLE public.resource_allocations (
  id BIGSERIAL PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL,

  direction TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  unit TEXT NOT NULL,
  allocation_reason TEXT NOT NULL,

  amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
  duration_days NUMERIC(10,2) NOT NULL CHECK (duration_days >= 0),

  source TEXT NOT NULL,
  confirmed BOOLEAN NOT NULL DEFAULT FALSE,
  notes TEXT
);

-- мінімальні індекси
CREATE INDEX idx_ra_occurred_at ON public.resource_allocations (occurred_at DESC);
CREATE INDEX idx_ra_direction   ON public.resource_allocations (direction);

-- (опційно, але корисно для фільтрів/heatmap)
CREATE INDEX idx_ra_resource_type ON public.resource_allocations (resource_type);
CREATE INDEX idx_ra_unit          ON public.resource_allocations (unit);

-- 500 тестових рядків за ~120 днів
INSERT INTO public.resource_allocations (
  occurred_at, direction, resource_type, unit, allocation_reason,
  amount, duration_days, source, confirmed, notes
)
SELECT
  NOW()
    - (random() * 120 || ' days')::interval
    - (random() * 24  || ' hours')::interval
    - (random() * 60  || ' minutes')::interval,

  (ARRAY['Північ','Південь','Схід','Захід','Центр'])[1 + floor(random()*5)::int],
  (ARRAY['Паливо','Боєприпаси','Медицина','Ремонт','Звʼязок','Провізія'])[1 + floor(random()*6)::int],
  (ARRAY['J1','J2','J3','J4','J5'])[1 + floor(random()*5)::int],
  (ARRAY['Поповнення','Планова ротація','Екстрене підсилення','Навчання','Перекидання'])[1 + floor(random()*5)::int],

  round((10 + random()*1990)::numeric, 2),
  round((1 + random()*29)::numeric, 2),

  (ARRAY['Штаб','Склад','Підрозділ','Суміжники','Розвідка'])[1 + floor(random()*5)::int],
  (random() < 0.70),
  (ARRAY['Без приміток','Потребує уточнення','Погоджено старшим','Терміново','Контроль виконання'])[1 + floor(random()*5)::int]
FROM generate_series(1, 500);

-- перевірка
SELECT COUNT(*) AS total_rows FROM public.resource_allocations;
