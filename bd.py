import pandas as pd
import sqlite3
from datetime import datetime
import re

class ScheduleDatabase:
    def __init__(self, db_name='schedule_database.db'):
        self.db_name = db_name
        self.conn = None
        
    def connect(self):
        self.conn = sqlite3.connect(self.db_name)
        return self.conn
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                teacher_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT UNIQUE NOT NULL,
                department TEXT NOT NULL,
                position TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_directions (
                direction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                program_name TEXT NOT NULL,
                education_level TEXT NOT NULL,
                education_form TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_code TEXT NOT NULL,
                group_number TEXT NOT NULL,
                direction_id INTEGER,
                student_count INTEGER,
                FOREIGN KEY (direction_id) REFERENCES study_directions (direction_id),
                UNIQUE(group_code, group_number)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS disciplines (
                discipline_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                semester INTEGER,
                direction_id INTEGER,
                FOREIGN KEY (direction_id) REFERENCES study_directions (direction_id),
                UNIQUE(name, direction_id, semester)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teaching_load (
                load_id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER,
                discipline_id INTEGER,
                group_id INTEGER,
                work_type TEXT NOT NULL,
                lecture_hours REAL DEFAULT 0,
                practice_hours REAL DEFAULT 0,
                lab_hours REAL DEFAULT 0,
                total_hours REAL NOT NULL,
                semester INTEGER,
                FOREIGN KEY (teacher_id) REFERENCES teachers (teacher_id),
                FOREIGN KEY (discipline_id) REFERENCES disciplines (discipline_id),
                FOREIGN KEY (group_id) REFERENCES study_groups (group_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                discipline_id INTEGER,
                group_id INTEGER,
                teacher_id INTEGER,
                day_of_week TEXT NOT NULL,
                class_number INTEGER NOT NULL,
                class_time TEXT NOT NULL,
                subject_details TEXT,
                location TEXT,
                is_remote BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (discipline_id) REFERENCES disciplines (discipline_id),
                FOREIGN KEY (group_id) REFERENCES study_groups (group_id),
                FOREIGN KEY (teacher_id) REFERENCES teachers (teacher_id)
            )
        ''')
        
        self.conn.commit()
    
    def clean_teacher_name(self, name):
        if pd.isna(name) or name == 'nan':
            return None
        return str(name).strip()
    
    def extract_group_info(self, group_data):
        if pd.isna(group_data) or group_data == 'nan':
            return None, None
        
        group_str = str(group_data).strip()
        if '-' in group_str:
            parts = group_str.split('-')
            if len(parts) >= 2:
                return parts[0], '-'.join(parts[1:])
        return group_str, group_str
    
    def parse_schedule_subject(self, subject_text):
        if pd.isna(subject_text) or subject_text == 'nan':
            return None, None, None
        
        text = str(subject_text)
        is_remote = 'дистанционно' in text.lower()
        
        location = None
        if ';' in text:
            parts = text.split(';')
            if len(parts) >= 3:
                location = parts[2].strip() if len(parts) > 2 else None
        
        return text, location, is_remote
    
    def load_workload_data(self, workload_file):
        print("Загрузка данных учебной нагрузки...")
        workload_df = pd.read_excel(workload_file)
        
        teachers_dict = {}
        directions_dict = {}
        groups_dict = {}
        disciplines_dict = {}
        
        for _, row in workload_df.iterrows():
            teacher_name = self.clean_teacher_name(row['Преподаватель'])
            if teacher_name and teacher_name not in teachers_dict:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO teachers (full_name, department, position)
                    VALUES (?, ?, ?)
                ''', (teacher_name, row['Кафедра'], row['Должность']))
                teachers_dict[teacher_name] = cursor.lastrowid
        
        for _, row in workload_df.iterrows():
            direction_key = f"{row['Код_направления']}_{row['Наименование_программы']}"
            if direction_key not in directions_dict:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO study_directions 
                    (code, name, program_name, education_level, education_form)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    row['Код_направления'], 
                    row['Наименование_программы'],
                    row['Наименование_программы'],
                    row['Уровень_ОП'],
                    row['Форма_обучения']
                ))
                directions_dict[direction_key] = cursor.lastrowid
        
        for _, row in workload_df.iterrows():
            group_code, group_number = self.extract_group_info(row['Номер_группы'])
            direction_key = f"{row['Код_направления']}_{row['Наименование_программы']}"
            
            if group_code and group_number and direction_key in directions_dict:
                group_key = f"{group_code}_{group_number}"
                if group_key not in groups_dict:
                    cursor = self.conn.cursor()
                    cursor.execute('''
                        INSERT OR IGNORE INTO study_groups 
                        (group_code, group_number, direction_id, student_count)
                        VALUES (?, ?, ?, ?)
                    ''', (group_code, group_number, directions_dict[direction_key], 
                          pd.to_numeric(row['Количество_студентов'], errors='coerce')))
                    groups_dict[group_key] = cursor.lastrowid
        
        for _, row in workload_df.iterrows():
            direction_key = f"{row['Код_направления']}_{row['Наименование_программы']}"
            discipline_key = f"{row['Дисциплина']}_{direction_key}_{row['Семестр']}"
            
            if discipline_key not in disciplines_dict and direction_key in directions_dict:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO disciplines 
                    (name, semester, direction_id)
                    VALUES (?, ?, ?)
                ''', (row['Дисциплина'], row['Семестр'], directions_dict[direction_key]))
                disciplines_dict[discipline_key] = cursor.lastrowid
        
        load_count = 0
        for _, row in workload_df.iterrows():
            teacher_name = self.clean_teacher_name(row['Преподаватель'])
            direction_key = f"{row['Код_направления']}_{row['Наименование_программы']}"
            group_code, group_number = self.extract_group_info(row['Номер_группы'])
            discipline_key = f"{row['Дисциплина']}_{direction_key}_{row['Семестр']}"
            
            if (teacher_name in teachers_dict and 
                direction_key in directions_dict and
                group_code and group_number and
                discipline_key in disciplines_dict):
                
                group_key = f"{group_code}_{group_number}"
                if group_key in groups_dict:
                    cursor = self.conn.cursor()
                    cursor.execute('''
                        INSERT INTO teaching_load 
                        (teacher_id, discipline_id, group_id, work_type, 
                         lecture_hours, practice_hours, lab_hours, total_hours, semester)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        teachers_dict[teacher_name],
                        disciplines_dict[discipline_key],
                        groups_dict[group_key],
                        row['Вид_работы'],
                        pd.to_numeric(row['Лекции_часы'], errors='coerce') or 0,
                        pd.to_numeric(row['Практика_часы'], errors='coerce') or 0,
                        pd.to_numeric(row['Лабораторные_часы'], errors='coerce') or 0,
                        pd.to_numeric(row['Всего_часов'], errors='coerce') or 0,
                        row['Семестр']
                    ))
                    load_count += 1
        
        self.conn.commit()
        print(f"Загружено {load_count} записей учебной нагрузки")
    
    def load_schedule_data(self, schedule_file):
        """Загрузка данных расписания"""
        print("Загрузка данных расписания...")
        schedule_df = pd.read_excel(schedule_file)
        
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT teacher_id, full_name FROM teachers")
        teachers = {row[1]: row[0] for row in cursor.fetchall()}
        
        cursor.execute("SELECT group_id, group_code, group_number FROM study_groups")
        groups = {}
        for row in cursor.fetchall():
            groups[f"{row[1]}-{row[2]}"] = row[0]  

        schedule_count = 0
        for _, row in schedule_df.iterrows():
            group_key = row['Учебная группа']
            group_id = groups.get(group_key)
            
            if not group_id:
                continue
            
            subject_text, location, is_remote = self.parse_schedule_subject(row['Предмет'])
            
            teacher_id = None
            if subject_text:
                for teacher_name, t_id in teachers.items():
                    if teacher_name in subject_text:
                        teacher_id = t_id
                        break
            
            cursor.execute('''
                INSERT INTO schedule 
                (group_id, teacher_id, day_of_week, class_number, class_time, 
                 subject_details, location, is_remote)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                group_id, teacher_id, row['День недели'], row['Пара'], 
                row['Время'], subject_text, location, is_remote
            ))
            schedule_count += 1
        
        self.conn.commit()
        print(f"Загружено {schedule_count} записей расписания")
    
    def create_views(self):
        """Создание полезных представлений"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE VIEW IF NOT EXISTS full_schedule_view AS
            SELECT 
                s.day_of_week,
                s.class_number,
                s.class_time,
                g.group_code || '-' || g.group_number as group_name,
                d.name as discipline_name,
                t.full_name as teacher_name,
                s.location,
                s.is_remote,
                sd.name as direction_name
            FROM schedule s
            LEFT JOIN study_groups g ON s.group_id = g.group_id
            LEFT JOIN study_directions sd ON g.direction_id = sd.direction_id
            LEFT JOIN teachers t ON s.teacher_id = t.teacher_id
            LEFT JOIN teaching_load tl ON s.teacher_id = tl.teacher_id AND s.group_id = tl.group_id
            LEFT JOIN disciplines d ON tl.discipline_id = d.discipline_id
        ''')
        
        cursor.execute('''
            CREATE VIEW IF NOT EXISTS teacher_workload_view AS
            SELECT 
                t.full_name,
                t.department,
                t.position,
                d.name as discipline,
                g.group_code || '-' || g.group_number as group_name,
                tl.work_type,
                tl.lecture_hours,
                tl.practice_hours,
                tl.lab_hours,
                tl.total_hours,
                tl.semester,
                sd.name as direction_name
            FROM teaching_load tl
            JOIN teachers t ON tl.teacher_id = t.teacher_id
            JOIN disciplines d ON tl.discipline_id = d.discipline_id
            JOIN study_groups g ON tl.group_id = g.group_id
            JOIN study_directions sd ON g.direction_id = sd.direction_id
        ''')
        
        self.conn.commit()
        print("Представления созданы")
    
    def generate_reports(self):
        """Генерация отчетов"""
        print("\n=== ОТЧЕТЫ ===")
        
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM teachers")
        teacher_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM study_groups")
        group_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM disciplines")
        discipline_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(total_hours) FROM teaching_load")
        total_hours = cursor.fetchone()[0] or 0
        
        print(f"Преподавателей: {teacher_count}")
        print(f"Учебных групп: {group_count}")
        print(f"Дисциплин: {discipline_count}")
        print(f"Общая нагрузка: {total_hours:.2f} часов")
        
        print("\nТоп-5 преподавателей по нагрузке:")
        cursor.execute('''
            SELECT t.full_name, SUM(tl.total_hours) as total
            FROM teaching_load tl
            JOIN teachers t ON tl.teacher_id = t.teacher_id
            GROUP BY t.teacher_id
            ORDER BY total DESC
            LIMIT 5
        ''')
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]:.2f} часов")
    
    def close(self):
        """Закрытие соединения с БД"""
        if self.conn:
            self.conn.close()

def main():
    db = ScheduleDatabase('university_schedule.db')
    db.connect()
    
    try:
        db.create_tables()
        
        db.load_workload_data("improved_un_svodnaya.xlsx")
        db.load_schedule_data("расписание_по_группам_с_направлением.xlsx")
        
        db.create_views()
        
        db.generate_reports()
        
        print(f"\nБаза данных успешно создана: university_schedule.db")
        print("Доступные таблицы: teachers, study_directions, study_groups, disciplines, teaching_load, schedule")
        print("Доступные представления: full_schedule_view, teacher_workload_view")
        
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()