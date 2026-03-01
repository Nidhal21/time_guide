#!/usr/bin/env python3
"""
Excel Parser for Emploi du Temps files
Parse student, professor, and class schedule Excel files
"""
import pandas as pd
import os
from datetime import datetime, time
from typing import Dict, List, Optional

class EmploiDuTempsParser:
    """Parser for university timetable Excel files"""
    
    def __init__(self):
        self.days_mapping = {
            'Lundi': 'Lundi',
            'Mardi': 'Mardi', 
            'Mercredi': 'Mercredi',
            'Jeudi': 'Jeudi',
            'Vendredi': 'Vendredi',
            'Samedi': 'Samedi',
            'Dimanche': 'Dimanche',
            'Monday': 'Lundi',
            'Tuesday': 'Mardi',
            'Wednesday': 'Mercredi', 
            'Thursday': 'Jeudi',
            'Friday': 'Vendredi',
            'Saturday': 'Samedi',
            'Sunday': 'Dimanche'
        }
        
    def parse_student_schedule(self, file_path: str) -> Dict:
        """Parse student schedule Excel file"""
        try:
            df = pd.read_excel(file_path, sheet_name=None)
            schedule_data = []
            
            for sheet_name, sheet_df in df.items():
                print(f"Processing sheet: {sheet_name}")
                
                # Skip empty sheets
                if sheet_df.empty:
                    continue
                
                # Find the schedule table (usually starts with time columns)
                time_cols = []
                for col in sheet_df.columns:
                    if any(str(col).startswith(str(h)) for h in ['08', '09', '10', '11', '12', '13', '14', '15', '16', '17']):
                        time_cols.append(col)
                
                if not time_cols:
                    print(f"No time columns found in sheet {sheet_name}")
                    continue
                
                # Find day rows
                day_rows = {}
                for idx, row in sheet_df.iterrows():
                    first_col = str(row.iloc[0]) if len(row) > 0 else ""
                    if any(day in first_col for day in self.days_mapping.keys()):
                        day_name = self.days_mapping.get(first_col.split()[0], first_col)
                        day_rows[day_name] = idx
                
                # Extract schedule data
                for day, row_idx in day_rows.items():
                    row = sheet_df.iloc[row_idx]
                    for time_col in time_cols:
                        cell_value = str(row[time_col]) if time_col in row else ""
                        if cell_value and cell_value not in ['nan', 'NaN', '']:
                            # Parse time
                            try:
                                start_time = self._parse_time(str(time_col))
                                end_time = self._add_hours(start_time, 1.5)  # Default 1.5h class
                            except:
                                continue
                            
                            # Parse course info
                            course_info = self._parse_course_cell(cell_value)
                            
                            schedule_data.append({
                                'jour': day,
                                'heure_debut': start_time,
                                'heure_fin': end_time,
                                'matiere': course_info.get('matiere', ''),
                                'professeur': course_info.get('professeur', ''),
                                'salle': course_info.get('salle', ''),
                                'type_seance': course_info.get('type', 'cours'),
                                'classe': sheet_name,
                                'source_file': os.path.basename(file_path)
                            })
            
            return {
                'success': True,
                'data': schedule_data,
                'total_records': len(schedule_data)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    def parse_professor_schedule(self, file_path: str) -> Dict:
        """Parse professor schedule Excel file"""
        try:
            df = pd.read_excel(file_path, sheet_name=None)
            professor_data = []
            
            for sheet_name, sheet_df in df.items():
                if sheet_df.empty:
                    continue
                
                # Assume professor name is in sheet name or first cell
                professor_name = sheet_name
                
                # Similar parsing logic as student schedule
                time_cols = []
                for col in sheet_df.columns:
                    if any(str(col).startswith(str(h)) for h in ['08', '09', '10', '11', '12', '13', '14', '15', '16', '17']):
                        time_cols.append(col)
                
                day_rows = {}
                for idx, row in sheet_df.iterrows():
                    first_col = str(row.iloc[0]) if len(row) > 0 else ""
                    if any(day in first_col for day in self.days_mapping.keys()):
                        day_name = self.days_mapping.get(first_col.split()[0], first_col)
                        day_rows[day_name] = idx
                
                for day, row_idx in day_rows.items():
                    row = sheet_df.iloc[row_idx]
                    for time_col in time_cols:
                        cell_value = str(row[time_col]) if time_col in row else ""
                        if cell_value and cell_value not in ['nan', 'NaN', '']:
                            try:
                                start_time = self._parse_time(str(time_col))
                                end_time = self._add_hours(start_time, 1.5)
                            except:
                                continue
                            
                            course_info = self._parse_course_cell(cell_value)
                            
                            professor_data.append({
                                'jour': day,
                                'heure_debut': start_time,
                                'heure_fin': end_time,
                                'matiere': course_info.get('matiere', ''),
                                'salle': course_info.get('salle', ''),
                                'classe': course_info.get('classe', ''),
                                'professeur': professor_name,
                                'type_seance': course_info.get('type', 'cours'),
                                'source_file': os.path.basename(file_path)
                            })
            
            return {
                'success': True,
                'data': professor_data,
                'total_records': len(professor_data)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    def parse_class_schedule(self, file_path: str) -> Dict:
        """Parse class schedule Excel file"""
        # Similar to student schedule but focused on class data
        return self.parse_student_schedule(file_path)
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object"""
        try:
            # Handle formats like "08:15", "08h15", "8:15"
            time_str = time_str.replace('h', ':').replace('H', ':')
            parts = time_str.split(':')
            if len(parts) >= 2:
                hour = int(parts[0])
                minute = int(parts[1].split('-')[0])  # Handle "08:15-09:45" format
                return time(hour, minute)
            else:
                # Handle just hour like "08"
                hour = int(time_str)
                return time(hour, 0)
        except:
            return time(8, 0)  # Default fallback
    
    def _add_hours(self, start_time: time, hours: float) -> time:
        """Add hours to time"""
        total_minutes = start_time.hour * 60 + start_time.minute + int(hours * 60)
        end_hour = (total_minutes // 60) % 24
        end_minute = total_minutes % 60
        return time(end_hour, end_minute)
    
    def _parse_course_cell(self, cell_value: str) -> Dict:
        """Parse course information from cell"""
        course_info = {
            'matiere': '',
            'professeur': '',
            'salle': '',
            'type': 'cours'
        }
        
        # Common patterns
        # "Matiere\nProfesseur\nSalle"
        # "Matiere - Prof - Salle"
        # "Matiere (Prof) Salle"
        
        lines = cell_value.split('\n')
        if len(lines) >= 3:
            course_info['matiere'] = lines[0].strip()
            course_info['professeur'] = lines[1].strip()
            course_info['salle'] = lines[2].strip()
        elif len(lines) == 2:
            course_info['matiere'] = lines[0].strip()
            # Try to extract professor and room from second line
            second_line = lines[1].strip()
            if any(char.isdigit() for char in second_line):
                # Likely contains room number
                course_info['salle'] = second_line
            else:
                course_info['professeur'] = second_line
        else:
            # Single line, try to parse with separators
            if '-' in cell_value:
                parts = cell_value.split('-')
                if len(parts) >= 2:
                    course_info['matiere'] = parts[0].strip()
                    course_info['professeur'] = parts[1].strip()
                    if len(parts) >= 3:
                        course_info['salle'] = parts[2].strip()
            else:
                course_info['matiere'] = cell_value.strip()
        
        # Detect course type
        cell_lower = cell_value.lower()
        if 'tp' in cell_lower:
            course_info['type'] = 'TP'
        elif 'td' in cell_lower:
            course_info['type'] = 'TD'
        elif 'cm' in cell_lower or 'cours' in cell_lower:
            course_info['type'] = 'cours'
        
        return course_info

def main():
    """Test the parser"""
    parser = EmploiDuTempsParser()
    
    # Example usage
    excel_files = [
        "public/excel_files/emploi_etudiant.xlsx",
        "public/excel_files/emploi_professeur.xlsx", 
        "public/excel_files/emploi_classes.xlsx"
    ]
    
    for file_path in excel_files:
        if os.path.exists(file_path):
            print(f"\n📊 Parsing {file_path}...")
            
            if "etudiant" in file_path or "class" in file_path:
                result = parser.parse_student_schedule(file_path)
            elif "professeur" in file_path:
                result = parser.parse_professor_schedule(file_path)
            else:
                result = parser.parse_class_schedule(file_path)
            
            if result['success']:
                print(f"✅ Successfully parsed {result['total_records']} records")
                for i, record in enumerate(result['data'][:3]):  # Show first 3
                    print(f"  {i+1}. {record['jour']} {record['heure_debut']}-{record['heure_fin']} | {record['matiere']}")
            else:
                print(f"❌ Error: {result['error']}")
        else:
            print(f"⚠️  File not found: {file_path}")

if __name__ == "__main__":
    main()
