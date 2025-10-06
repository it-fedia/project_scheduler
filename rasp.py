import pandas as pd
file_path = r"C:\Users\User\ФМиЕН_ расписание 3 модуль_2025_бакалавры (1).xlsx"

xls = pd.ExcelFile(file_path)
df = pd.read_excel(xls, sheet_name="ФМиЕН")

data = df.iloc[4:]
data = data.rename(columns={
    'Unnamed: 1': 'День недели',
    'Unnamed: 2': 'Пара',
    'Unnamed: 3': 'Время'
})

rows = []

for col in data.columns[4:]:
    column_data = df[col].tolist()
    if len(column_data) >= 4:
        group_code = column_data[3]
        direction_code = column_data[1]
        direction_name_full = str(column_data[2])

        if pd.isna(group_code) or pd.isna(direction_code) or pd.isna(direction_name_full):
            continue

        if "\n" in direction_name_full:
            direction_name, speciality = direction_name_full.split("\n", 1)
        else:
            direction_name = direction_name_full
            speciality = direction_name_full  

        for idx, row in data.iterrows():
            if pd.notna(row[col]) and isinstance(row[col], str):
                rows.append({
                    "День недели": row["День недели"],
                    "Пара": row["Пара"],
                    "Время": row["Время"],
                    "Код направления": direction_code.strip(),
                    "Название направления": direction_name.strip(),
                    "Специальность": speciality.strip(),
                    "Учебная группа": group_code.strip(),
                    "Предмет": row[col].strip()
                })

schedule_df = pd.DataFrame(rows)

schedule_df.to_excel("расписание_по_группам_с_направлением.xlsx", index=False)
