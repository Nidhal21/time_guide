#!/usr/bin/env python3
"""
Comprehensive Database Viewer for Emploi du Temps System
Shows all tables, relationships, and data
"""
import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()

class DatabaseViewer:
    """Complete database inspection tool"""
    
    def __init__(self):
        self.conn = psycopg2.connect(
            host="127.0.0.1",
            port=5432,
            database="emploi_temps",
            user="emploi_user",
            password="emploi_temps"
        )
        self.cursor = self.conn.cursor()
    
    def show_all_tables(self):
        """Show overview of all tables"""
        print("🗄️  DATABASE OVERVIEW")
        print("=" * 80)
        
        self.cursor.execute("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = self.cursor.fetchall()
        
        print(f"📊 Found {len(tables)} tables:")
        for table, col_count in tables:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = self.cursor.fetchone()[0]
            print(f"  📋 {table:25} | {row_count:4d} rows | {col_count:2d} columns")
    
    def show_table_structure(self, table_name):
        """Show detailed structure of a specific table"""
        print(f"\n🔍 TABLE: {table_name}")
        print("-" * 60)
        
        # Get columns
        self.cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        columns = self.cursor.fetchall()
        
        print("Columns:")
        print(f"  {'Name':20} {'Type':15} {'Nullable':8} {'Default'}")
        print("  " + "-" * 60)
        for col in columns:
            nullable = "YES" if col[2] == "YES" else "NO"
            default = str(col[3]) if col[3] else ""
            print(f"  {col[0]:20} {col[1]:15} {nullable:8} {default}")
        
        # Get sample data
        self.cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        rows = self.cursor.fetchall()
        
        if rows:
            print(f"\nSample data ({len(rows)} of {self._get_row_count(table_name)} total):")
            # Print headers
            col_names = [desc[0] for desc in self.cursor.description]
            header = " | ".join(f"{name:15}" for name in col_names)
            print(f"  {header}")
            print("  " + "-" * len(header))
            
            # Print rows
            for row in rows:
                values = [str(val)[:15] if val is not None else "NULL" for val in row]
                line = " | ".join(f"{val:15}" for val in values)
                print(f"  {line}")
    
    def show_relationships(self):
        """Show table relationships and foreign keys"""
        print("\n🔗 TABLE RELATIONSHIPS")
        print("=" * 80)
        
        self.cursor.execute("""
            SELECT 
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
        """)
        
        fks = self.cursor.fetchall()
        if fks:
            print("Foreign Keys:")
            for fk in fks:
                print(f"  {fk[0]}.{fk[1]} → {fk[2]}.{fk[3]}")
        else:
            print("No foreign key constraints found")
    
    def show_current_schedule(self):
        """Show current academic schedule context"""
        print("\n📅 CURRENT ACADEMIC CONTEXT")
        print("=" * 80)
        
        # Get current period
        self.cursor.execute("""
            SELECT 
                au.libelle as annee,
                s.nom as semestre,
                p.nom as periode,
                p.date_debut,
                p.date_fin,
                CURRENT_DATE as today
            FROM periodes p
            JOIN semestres s ON p.semestre_id = s.id
            JOIN annees_universitaires au ON s.annee_id = au.id
            WHERE CURRENT_DATE BETWEEN p.date_debut AND p.date_fin
        """)
        
        context = self.cursor.fetchone()
        if context:
            print(f"Année: {context[0]}")
            print(f"Semestre: {context[1]}")
            print(f"Période: {context[2]}")
            print(f"Du {context[3]} au {context[4]}")
            print(f"Aujourd'hui: {context[5]}")
            
            # Show tomorrow
            self.cursor.execute("SELECT CURRENT_DATE + INTERVAL '1 day'")
            tomorrow = self.cursor.fetchone()[0]
            print(f"Demain: {tomorrow}")
        else:
            print("No active period found")
    
    def show_class_schedule(self, class_name):
        """Show schedule for a specific class"""
        print(f"\n🎓 SCHEDULE FOR: {class_name}")
        print("=" * 80)
        
        # Find class
        self.cursor.execute("SELECT id, nom FROM classes WHERE nom ILIKE %s", (f"%{class_name}%",))
        classes = self.cursor.fetchall()
        
        if not classes:
            print(f"❌ Class '{class_name}' not found")
            return
        
        for class_id, full_name in classes:
            print(f"\n📚 {full_name} (ID: {class_id})")
            
            # Get schedule
            self.cursor.execute("""
                SELECT 
                    s.jour,
                    s.heure_debut,
                    s.heure_fin,
                    m.nom as matiere,
                    p.nom_complet as professeur,
                    sa.nom as salle,
                    s.type_seance
                FROM seances s
                JOIN matieres m ON s.matiere_id = m.id
                JOIN professeurs p ON s.professeur_id = p.id
                JOIN salles sa ON s.salle_id = sa.id
                WHERE s.classe_id = %s
                ORDER BY s.jour, s.heure_debut
            """, (class_id,))
            
            seances = self.cursor.fetchall()
            
            if seances:
                # Group by day
                by_day = {}
                for s in seances:
                    day = s[0]
                    if day not in by_day:
                        by_day[day] = []
                    by_day[day].append(s[1:])
                
                days_order = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
                for day in days_order:
                    if day in by_day:
                        print(f"\n  📅 {day}:")
                        for s in by_day[day]:
                            print(f"    {s[0]}-{s[1]} | {s[2]} | Prof: {s[3]} | Salle: {s[4]} | {s[5]}")
            else:
                print("  ❌ No schedule found")
    
    def show_professor_schedule(self, prof_name):
        """Show schedule for a specific professor"""
        print(f"\n👨‍🏫 SCHEDULE FOR PROFESSOR: {prof_name}")
        print("=" * 80)
        
        self.cursor.execute("SELECT id, nom_complet FROM professeurs WHERE nom_complet ILIKE %s", (f"%{prof_name}%",))
        profs = self.cursor.fetchall()
        
        if not profs:
            print(f"❌ Professor '{prof_name}' not found")
            return
        
        for prof_id, full_name in profs:
            print(f"\n👨‍🏫 {full_name} (ID: {prof_id})")
            
            self.cursor.execute("""
                SELECT 
                    s.jour,
                    s.heure_debut,
                    s.heure_fin,
                    m.nom as matiere,
                    c.nom as classe,
                    sa.nom as salle,
                    s.type_seance
                FROM seances s
                JOIN matieres m ON s.matiere_id = m.id
                JOIN classes c ON s.classe_id = c.id
                JOIN salles sa ON s.salle_id = sa.id
                WHERE s.professeur_id = %s
                ORDER BY s.jour, s.heure_debut
            """, (prof_id,))
            
            seances = self.cursor.fetchall()
            
            if seances:
                by_day = {}
                for s in seances:
                    day = s[0]
                    if day not in by_day:
                        by_day[day] = []
                    by_day[day].append(s[1:])
                
                days_order = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
                for day in days_order:
                    if day in by_day:
                        print(f"\n  📅 {day}:")
                        for s in by_day[day]:
                            print(f"    {s[0]}-{s[1]} | {s[2]} | {s[3]} | Salle: {s[4]} | {s[5]}")
            else:
                print("  ❌ No schedule found")
    
    def show_room_schedule(self, room_name):
        """Show schedule for a specific room"""
        print(f"\n🏢 SCHEDULE FOR ROOM: {room_name}")
        print("=" * 80)
        
        self.cursor.execute("SELECT id, nom FROM salles WHERE nom ILIKE %s", (f"%{room_name}%",))
        rooms = self.cursor.fetchall()
        
        if not rooms:
            print(f"❌ Room '{room_name}' not found")
            return
        
        for room_id, full_name in rooms:
            print(f"\n🏢 {full_name} (ID: {room_id})")
            
            self.cursor.execute("""
                SELECT 
                    s.jour,
                    s.heure_debut,
                    s.heure_fin,
                    m.nom as matiere,
                    c.nom as classe,
                    p.nom_complet as professeur,
                    s.type_seance
                FROM seances s
                JOIN matieres m ON s.matiere_id = m.id
                JOIN classes c ON s.classe_id = c.id
                JOIN professeurs p ON s.professeur_id = p.id
                WHERE s.salle_id = %s
                ORDER BY s.jour, s.heure_debut
            """, (room_id,))
            
            seances = self.cursor.fetchall()
            
            if seances:
                by_day = {}
                for s in seances:
                    day = s[0]
                    if day not in by_day:
                        by_day[day] = []
                    by_day[day].append(s[1:])
                
                days_order = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
                for day in days_order:
                    if day in by_day:
                        print(f"\n  📅 {day}:")
                        for s in by_day[day]:
                            print(f"    {s[0]}-{s[1]} | {s[2]} | {s[3]} | Prof: {s[4]} | {s[5]}")
            else:
                print("  ❌ No schedule found")
    
    def export_database_schema(self):
        """Export complete database schema to JSON"""
        schema = {}
        
        self.cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        tables = [row[0] for row in self.cursor.fetchall()]
        
        for table in tables:
            schema[table] = {
                'columns': [],
                'row_count': self._get_row_count(table),
                'sample_data': []
            }
            
            # Get columns
            self.cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            schema[table]['columns'] = [
                {'name': row[0], 'type': row[1], 'nullable': row[2]}
                for row in self.cursor.fetchall()
            ]
            
            # Get sample data
            self.cursor.execute(f"SELECT * FROM {table} LIMIT 3")
            rows = self.cursor.fetchall()
            col_names = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                schema[table]['sample_data'].append(
                    dict(zip(col_names, row))
                )
        
        # Save to file
        with open('database_schema.json', 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"📄 Schema exported to database_schema.json")
    
    def _get_row_count(self, table_name):
        """Get row count for a table"""
        self.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return self.cursor.fetchone()[0]
    
    def close(self):
        """Close database connection"""
        self.cursor.close()
        self.conn.close()

def main():
    """Interactive database viewer"""
    viewer = DatabaseViewer()
    
    try:
        while True:
            print("\n" + "="*80)
            print("🗄️  EMPLOI DU TEMPS DATABASE VIEWER")
            print("="*80)
            print("1. Show all tables overview")
            print("2. Show table structure")
            print("3. Show relationships")
            print("4. Show current academic context")
            print("5. Show class schedule")
            print("6. Show professor schedule")
            print("7. Show room schedule")
            print("8. Export database schema")
            print("9. Exit")
            
            choice = input("\nChoose option (1-9): ").strip()
            
            if choice == '1':
                viewer.show_all_tables()
            elif choice == '2':
                table = input("Enter table name: ").strip()
                viewer.show_table_structure(table)
            elif choice == '3':
                viewer.show_relationships()
            elif choice == '4':
                viewer.show_current_schedule()
            elif choice == '5':
                class_name = input("Enter class name (e.g., '2 ING GII 3'): ").strip()
                viewer.show_class_schedule(class_name)
            elif choice == '6':
                prof_name = input("Enter professor name: ").strip()
                viewer.show_professor_schedule(prof_name)
            elif choice == '7':
                room_name = input("Enter room name: ").strip()
                viewer.show_room_schedule(room_name)
            elif choice == '8':
                viewer.export_database_schema()
            elif choice == '9':
                break
            else:
                print("❌ Invalid choice")
            
            input("\nPress Enter to continue...")
    
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    finally:
        viewer.close()

if __name__ == "__main__":
    main()
