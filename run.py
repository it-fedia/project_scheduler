import pandas as pd
import numpy as np
from collections import defaultdict
import re

def load_and_preprocess_data(file_path):
    dtype_optimization = {
        'Форма обучения ': 'category',
        '  Уровень ОП(Образовательная программа) ': 'category', 
        '  Вид учебной работы ': 'category',
        ' Сведения о ППС Кафедра/департамент ': 'category',
        '  должность ': 'category'
    }
    
    excel_data = pd.read_excel(file_path, sheet_name="УН сводная", header=None)
    
    header_rows = excel_data.iloc[:4]
    combined_headers = header_rows.ffill().bfill().iloc[0].astype(str) + " " + \
                      header_rows.ffill().bfill().iloc[1].astype(str) + " " + \
                      header_rows.ffill().bfill().iloc[2].astype(str) + " " + \
                      header_rows.ffill().bfill().iloc[3].astype(str)
    combined_headers = combined_headers.str.strip()
    
    df = excel_data.iloc[4:].copy()
    df.columns = combined_headers
    
    return df, combined_headers

def optimize_column_mapping(df_columns, column_mapping):
    existing_columns = {}
    compiled_patterns = {}
    
    for old_col in column_mapping.keys():
        pattern = re.escape(old_col.strip())
        compiled_patterns[old_col] = re.compile(pattern, re.IGNORECASE)
    
    available_columns_set = set(df_columns)
    
    for old_col, new_col in column_mapping.items():
        pattern = compiled_patterns[old_col]
        found_columns = [col for col in available_columns_set if pattern.search(col)]
        if found_columns:
            existing_columns[found_columns[0]] = new_col
            print(f"Найдена колонка: '{found_columns[0]}' -> '{new_col}'")
    
    return existing_columns

def fast_data_filtering(df_selected):
    if 'Преподаватель' not in df_selected.columns:
        return df_selected
    
    teacher_series = df_selected['Преподаватель'].astype(str).str.strip()
    
    valid_teachers_mask = (
        (teacher_series != 'nan') & 
        (teacher_series != '') &
        (~teacher_series.str.match(r'^\d+\.?\d*$', na=False)) &
        (teacher_series.str.len() > 1)
    )
    
    return df_selected[valid_teachers_mask].copy()

def optimize_memory_usage(df):
    for col in df.columns:
        if df[col].dtype == 'object':
            if df[col].nunique() / len(df) < 0.5: 
                df[col] = df[col].astype('category')
        elif df[col].dtype in ['int64', 'float64']:
            if pd.api.types.is_integer_dtype(df[col]):
                df[col] = pd.to_numeric(df[col], downcast='integer')
            else:
                df[col] = pd.to_numeric(df[col], downcast='float')
    
    return df

def efficient_groupby_operations(df_selected):
    numeric_columns = ['Лекции_часы', 'Практика_часы', 'Лабораторные_часы', 'Всего_часов']
    
    for col in numeric_columns:
        if col in df_selected.columns:
            df_selected[col] = pd.to_numeric(df_selected[col], errors='coerce').fillna(0)
    
    aggregation_config = {}
    
    if 'Дисциплина' in df_selected.columns:
        aggregation_config['Дисциплина'] = 'nunique'
    
    if 'Номер_группы' in df_selected.columns:
        aggregation_config['Номер_группы'] = 'count'
    
    for col in numeric_columns:
        if col in df_selected.columns:
            aggregation_config[col] = 'sum'
    
    if aggregation_config and 'Преподаватель' in df_selected.columns:
        teacher_summary = (
            df_selected
            .groupby('Преподаватель', observed=True) 
            .agg(aggregation_config)
            .reset_index()
        )
        
        column_rename_map = {
            'Дисциплина': 'Количество_дисциплин',
            'Номер_группы': 'Количество_групп',
            'Лекции_часы': 'Сумма_лекций', 
            'Практика_часы': 'Сумма_практик',
            'Лабораторные_часы': 'Сумма_лабораторных',
            'Всего_часов': 'Общая_нагрузка'
        }
        
        teacher_summary = teacher_summary.rename(columns={
            k: v for k, v in column_rename_map.items() if k in teacher_summary.columns
        })
        
        if 'Общая_нагрузка' in teacher_summary.columns:
            teacher_summary = teacher_summary.sort_values('Общая_нагрузка', ascending=False)
        
        return teacher_summary
    
    return None

def parallel_discipline_processing(df_selected):
    if 'Дисциплина' not in df_selected.columns or 'Преподаватель' not in df_selected.columns:
        return None
    
    groupby_cols = ['Преподаватель', 'Дисциплина']
    agg_dict = {}
    
    if 'Вид_работы' in df_selected.columns:
        agg_dict['Вид_работы'] = 'first'
    if 'Семестр' in df_selected.columns:
        agg_dict['Семестр'] = 'first' 
    if 'Всего_часов' in df_selected.columns:
        agg_dict['Всего_часов'] = 'sum'
    
    disciplines_by_teacher = (
        df_selected
        .groupby(groupby_cols, observed=True)
        .agg(agg_dict)
        .reset_index()
    )
    
    return disciplines_by_teacher

def main():
    file_path = r"РУН ППС_24-25 (ММиИИ)_13.01.2025.xlsx"
    
    print("=== ЗАГРУЗКА ДАННЫХ ===")
    df, combined_headers = load_and_preprocess_data(file_path)
    print(f"Размер данных: {df.shape}")
    
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
    
    print("\n=== ОБРАБОТКА КОЛОНОК ===")
    existing_columns = optimize_column_mapping(df.columns, column_mapping)
    print(f"Будет извлечено {len(existing_columns)} колонок")
    
    df_selected = df[list(existing_columns.keys())].copy()
    df_selected.columns = list(existing_columns.values())
    
    print(f"Исходное количество строк: {len(df_selected)}")
    
    df_selected = optimize_memory_usage(df_selected)
    
    df_selected = fast_data_filtering(df_selected)
    print(f"Отфильтровано строк с преподавателями: {len(df_selected)}")
    
    if len(df_selected) == 0:
        print("Не найдено данных с преподавателями")
        return
    
    unique_teachers = df_selected['Преподаватель'].unique()
    print(f"\nНайдено уникальных преподавателей: {len(unique_teachers)}")
    print("Первые 10 преподавателей:")
    for i, teacher in enumerate(unique_teachers[:10]):
        print(f"  {i+1}: {teacher}")
    
    print("\n=== АНАЛИЗ ДАННЫХ ===")
    teacher_summary = efficient_groupby_operations(df_selected)
    disciplines_by_teacher = parallel_discipline_processing(df_selected)
    
    output_path = "improved_un_svodnaya.xlsx"
    df_selected.to_excel(output_path, index=False)
    print(f"Основной файл сохранен как: {output_path}")
    
    if teacher_summary is not None:
        teacher_summary.to_excel("сводка_по_преподавателям.xlsx", index=False)
        print("Сводка по преподавателям сохранена")
    
    if disciplines_by_teacher is not None:
        disciplines_by_teacher.to_excel("дисциплины_по_преподавателям.xlsx", index=False)
        print("Детализация по дисциплинам сохранена")

    print(f"\n=== ИТОГОВАЯ СТАТИСТИКА ===")
    print(f"Всего записей: {len(df_selected)}")
    print(f"Уникальных преподавателей: {len(unique_teachers)}")
    
    if 'Дисциплина' in df_selected.columns:
        print(f"Уникальных дисциплин: {df_selected['Дисциплина'].nunique()}")
    
    if 'Всего_часов' in df_selected.columns:
        total_hours = df_selected['Всего_часов'].sum()
        print(f"Общая нагрузка: {total_hours:.2f} часов")
    
    if teacher_summary is not None:
        print(f"\nТоп-5 преподавателей по нагрузке:")
        print(teacher_summary.head())
    
    print(f"\nИтоговые колонки: {list(df_selected.columns)}")
    
    print(f"\n=== ИНФОРМАЦИЯ О ПАМЯТИ ===")
    memory_usage = df_selected.memory_usage(deep=True).sum() / 1024**2  
    print(f"Использование памяти: {memory_usage:.2f} MB")

if __name__ == "__main__":
    main()