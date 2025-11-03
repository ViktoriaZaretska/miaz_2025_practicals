# excel_processor.py
import pandas as pd

# Прочитати Excel
df = pd.read_excel("data.xlsx")

# Приклад фільтра: залишити тільки Score > 80
if "Score" not in df.columns:
    raise SystemExit("У файлі має бути стовпець 'Score'")

filtered = df[df["Score"] > 80]

# Зберегти результат
filtered.to_excel("filtered_data.xlsx", index=False)
print(f"Збережено {len(filtered)} рядків у filtered_data.xlsx")
