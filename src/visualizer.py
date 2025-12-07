import csv
import json
import os
from collections import defaultdict

def load_json(base_path, subdir, filename):
    with open(os.path.join(base_path, subdir, filename), 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_html(cycle_num, output_path):
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Load data
    grupos = load_json(base_path, 'data', 'grupos.json')
    config = load_json(base_path, '', 'config.json')
    
    # Filter groups for this cycle
    cycle_groups = [g for g in grupos if g['ciclo'] == cycle_num]
    cycle_group_ids = set(g['id'] for g in cycle_groups)
    
    # Load schedule
    schedule = []
    csv_path = os.path.join(base_path, 'horario_generado.csv')
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Grupo'] in cycle_group_ids:
                schedule.append(row)

    # Time slot mapping
    slot_map = {}
    for i, slot in enumerate(config['time_slots']):
        start, end = slot.split('-')
        slot_map[start] = i

    # 1. Determine columns per day
    # Map: Day -> Slot -> List of Rows
    day_slot_events = defaultdict(lambda: defaultdict(list))
    
    for row in schedule:
        day = row['Dia']
        start_time = row['Hora Inicio']
        if start_time not in slot_map: continue
        
        start_idx = slot_map[start_time]
        
        # Calculate duration
        end_time = row['Hora Fin']
        duration = 0
        curr = start_idx
        while curr < len(config['time_slots']):
            s_end = config['time_slots'][curr].split('-')[1]
            duration += 1
            if s_end == end_time: break
            curr += 1
            
        # Add to all covered slots (NO ROWSPAN, so we need it in every slot)
        for d in range(duration):
            if start_idx + d < len(config['time_slots']):
                day_slot_events[day][start_idx + d].append(row)

    # Calculate max overlap per day to determine columns
    day_cols = {}
    days = config['days']
    
    for day in days:
        max_overlap = 1
        for slot_idx in range(len(config['time_slots'])):
            events = day_slot_events[day][slot_idx]
            # We need to count how many distinct "lanes" we need.
            # If we have 2 events, we need 2 cols.
            if len(events) > max_overlap:
                max_overlap = len(events)
        day_cols[day] = max_overlap

    # Helper to generate consistent pastel color from string
    def get_color(text):
        import hashlib
        hash_val = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
        h = hash_val % 360
        s = 70 + (hash_val % 20) # 70-90% saturation
        l = 85 + (hash_val % 10) # 85-95% lightness
        return f"hsl({h}, {s}%, {l}%)"

    # HTML Generation
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Horario Ciclo {cycle_num}</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; }}
            h1 {{ text-align: center; color: #333; }}
            table {{ border-collapse: collapse; width: 100%; box-shadow: 0 0 20px rgba(0,0,0,0.1); }}
            th, td {{ border: 1px solid #ccc; padding: 4px; text-align: center; vertical-align: middle; font-size: 0.85em; }}
            th {{ background-color: #2196f3; color: white; text-transform: uppercase; height: 40px; }}
            .slot-time {{ font-weight: bold; color: #555; background: #f9f9f9; width: 80px; }}
            .cell-content {{ 
                padding: 2px; 
            }}
            .break {{ background-color: #fff3e0; color: #e65100; font-weight: bold; height: 30px; }}
        </style>
    </head>
    <body>
        <h1>Horario Ciclo {cycle_num}</h1>
        <table>
            <thead>
                <tr>
                    <th>Hora</th>
    """
    
    for day in days:
        cols = day_cols[day]
        html += f"<th colspan='{cols}'>{day}</th>"
    html += "</tr></thead><tbody>"

    for i, slot in enumerate(config['time_slots']):
        if i in config.get('break_slots', []):
             total_cols = sum(day_cols.values()) + 1
             html += f"<tr class='break'><td class='slot-time'>{slot}</td><td colspan='{total_cols - 1}'>REFRIGERIO</td></tr>"
             continue

        html += f"<tr><td class='slot-time'>{slot}</td>"
        
        for day in days:
            events = day_slot_events[day][i]
            cols_needed = day_cols[day]
            
            # Sort events to keep consistent order (e.g. Group A always left)
            events.sort(key=lambda x: x['Grupo'])
            
            # If no events, render empty cells
            if not events:
                for _ in range(cols_needed):
                    html += "<td></td>"
                continue
                
            # If we have events, distribute them.
            if len(events) == 1 and cols_needed > 1:
                # Heuristic: Check if group ID ends with -A, -B, -C.
                g_id = events[0]['Grupo']
                is_section = g_id.endswith('-A') or g_id.endswith('-B') or g_id.endswith('-C')
                
                prof_name = events[0]['Profesor']
                bg_color = get_color(prof_name)
                
                if not is_section:
                    # Full span
                    html += f"<td colspan='{cols_needed}' style='background-color: {bg_color}'>"
                    html += f"<strong>{events[0]['Curso']}</strong><br>{events[0]['Grupo']}<br>{prof_name}<br>{events[0]['Aula']}"
                    html += "</td>"
                else:
                    # No span, fill first col, empty rest
                    html += f"<td style='background-color: {bg_color}'>"
                    html += f"<strong>{events[0]['Curso']}</strong><br>{events[0]['Grupo']}<br>{prof_name}<br>{events[0]['Aula']}"
                    html += "</td>"
                    for _ in range(cols_needed - 1):
                        html += "<td></td>"
            else:
                # Multiple events or 1 event in 1 col
                for idx in range(cols_needed):
                    if idx < len(events):
                        e = events[idx]
                        prof_name = e['Profesor']
                        bg_color = get_color(prof_name)
                        html += f"<td style='background-color: {bg_color}'>"
                        html += f"<strong>{e['Curso']}</strong><br>{e['Grupo']}<br>{prof_name}<br>{e['Aula']}"
                        html += "</td>"
                    else:
                        html += "<td></td>"
            
        html += "</tr>"

    html += """
        </tbody>
        </table>
    </body>
    </html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Generated {output_path}")

if __name__ == "__main__":
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    grupos = load_json(base_path, 'data', 'grupos.json')
    
    # Get unique cycles
    cycles = sorted(list(set(g['ciclo'] for g in grupos)))
    
    print(f"Generando horarios para los ciclos: {cycles}")
    
    for cycle in cycles:
        output_file = f"horario_ciclo_{cycle}.html"
        generate_html(cycle, output_file)
