import pandas as pd

file_path = r"C:\Users\User\РУН ППС_24-25 (ММиИИ)_13.01.2025.xlsx"
excel_data = pd.read_excel(file_path, sheet_name="УН сводная", header=None)

header_rows = excel_data.iloc[:4]
combined_headers = header_rows.fillna("").astype(str).agg(" ".join)

df = excel_data.iloc[4:].copy()
df.columns = combined_headers

print("Размер данных:", df.shape)

column_mapping = {
    'Форма обучения ': 'Форма_обучения',
    '  Уровень ОП(Образовательная программа) ': 'Уровень_ОП',
    '   Код направления': 'Код_направления', 
    '   Наименование программы': 'Наименование_программы',
    '   Наименование дисциплины или вида учебной работы': 'Дисциплина',
    '  Семестр ; Модуль ': 'Семестр',
    '  Вид учебной работы ': 'Вид_работы',
    ' Учебная группа \n(поток) Код': 'Код_группы',
    '   Номер группы': 'Номер_группы',
    '  Кол-во чел. в группе (потоке) Всего': 'Количество_студентов',
    ' Сведения о ППС Кафедра/департамент ': 'Кафедра',
    '  должность ': 'Должность',
    '  Фамилия И.О.  преподавателя ': 'Преподаватель',
    ' Объём учебной работы ППС Лекции ': 'Лекции_часы',
    ' Практика / Семинары ': 'Практика_часы',
    ' Лаб. работы / Клинические занятия ': 'Лабораторные_часы',
    ' ИТОГО  ': 'Всего_часов'
}

existing_columns = {}
for old_col, new_col in column_mapping.items():
    for df_col in df.columns:
        if old_col in df_col:
            existing_columns[df_col] = new_col
            print(f"Найдена колонка: '{df_col}' -> '{new_col}'")
            break

print(f"\nБудет извлечено {len(existing_columns)} колонок")

df_selected = df[list(existing_columns.keys())].copy()
df_selected.columns = list(existing_columns.values())

print(f"Исходное количество строк: {len(df_selected)}")

text_columns = ['Преподаватель', 'Дисциплина', 'Код_группы', 'Номер_группы', 'Кафедра', 'Должность']
for col in text_columns:
    if col in df_selected.columns:
        df_selected[col] = df_selected[col].astype(str).str.strip()

if 'Преподаватель' in df_selected.columns:
    df_selected = df_selected[
        (df_selected['Преподаватель'] != 'nan') & 
        (df_selected['Преподаватель'] != '') &
        (~df_selected['Преподаватель'].str.contains(r'^\d+\.?\d*$', na=False))
    ]

print(f"Отфильтровано строк с преподавателями: {len(df_selected)}")

if len(df_selected) > 0:
    unique_teachers = df_selected['Преподаватель'].unique()
    print(f"\nНайдено уникальных преподавателей: {len(unique_teachers)}")
    print("Первые 10 преподавателей:")
    for i, teacher in enumerate(unique_teachers[:10]):
        print(f"  {i+1}: {teacher}")
    
    numeric_columns = ['Лекции_часы', 'Практика_часы', 'Лабораторные_часы', 'Всего_часов']
    for col in numeric_columns:
        if col in df_selected.columns:
            df_selected[col] = pd.to_numeric(df_selected[col], errors='coerce')
    
    print("\nПервые 3 строки данных:")
    print(df_selected.head(3))
    
    output_path = "improved_un_svodnaya.xlsx"
    df_selected.to_excel(output_path, index=False)
    print(f"\nФайл сохранен как: {output_path}")
    
    available_columns = df_selected.columns.tolist()
    print(f"\nДоступные колонки: {available_columns}")
    
    agg_dict = {}
    
    if 'Дисциплина' in available_columns:
        agg_dict['Дисциплина'] = 'nunique'
    
    if 'Номер_группы' in available_columns:
        agg_dict['Номер_группы'] = 'count'
    
    numeric_agg_columns = ['Лекции_часы', 'Практика_часы', 'Лабораторные_часы', 'Всего_часов']
    for col in numeric_agg_columns:
        if col in available_columns:
            agg_dict[col] = 'sum'
    
    teacher_summary = df_selected.groupby('Преподаватель').agg(agg_dict).reset_index()
    
    new_column_names = ['Преподаватель']
    if 'Дисциплина' in agg_dict:
        new_column_names.append('Количество_дисциплин')
    if 'Номер_группы' in agg_dict:
        new_column_names.append('Количество_групп')
    if 'Лекции_часы' in agg_dict:
        new_column_names.append('Сумма_лекций')
    if 'Практика_часы' in agg_dict:
        new_column_names.append('Сумма_практик')
    if 'Лабораторные_часы' in agg_dict:
        new_column_names.append('Сумма_лабораторных')
    if 'Всего_часов' in agg_dict:
        new_column_names.append('Общая_нагрузка')
    
    teacher_summary.columns = new_column_names

    if 'Общая_нагрузка' in teacher_summary.columns:
        teacher_summary = teacher_summary.sort_values('Общая_нагрузка', ascending=False)
    
    teacher_summary.to_excel("сводка_по_преподавателям.xlsx", index=False)
    print("Сводка по преподавателям сохранена")

    if 'Дисциплина' in available_columns:
        disciplines_by_teacher = df_selected.groupby(['Преподаватель', 'Дисциплина']).agg({
            'Вид_работы': 'first',
            'Семестр': 'first',
            'Всего_часов': 'sum' if 'Всего_часов' in available_columns else None
        }).reset_index()
        
        disciplines_by_teacher.to_excel("дисциплины_по_преподавателям.xlsx", index=False)
        print("Детализация по дисциплинам сохранена")
    
    print(f"\n=== СТАТИСТИКА ===")
    print(f"Всего записей: {len(df_selected)}")
    print(f"Уникальных преподавателей: {len(unique_teachers)}")
    if 'Дисциплина' in available_columns:
        print(f"Уникальных дисциплин: {df_selected['Дисциплина'].nunique()}")
    if 'Всего_часов' in available_columns:
        print(f"Общая нагрузка: {df_selected['Всего_часов'].sum():.2f} часов")
    
    print(f"\nТоп-5 преподавателей по нагрузке:")
    print(teacher_summary.head())
    
else:
    print("Не найдено данных с преподавателями")

print(f"\nИтоговые колонки: {list(df_selected.columns)}")