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

    # --- IMPROVED COLOR PALETTE (EXTENDED) ---
    PALETTE = [
        "hsl(0, 85%, 90%)", "hsl(10, 85%, 90%)", "hsl(20, 85%, 90%)", "hsl(30, 85%, 90%)", 
        "hsl(40, 85%, 90%)", "hsl(50, 85%, 90%)", "hsl(60, 85%, 90%)", "hsl(70, 85%, 90%)",
        "hsl(80, 85%, 90%)", "hsl(90, 85%, 90%)", "hsl(100, 85%, 90%)", "hsl(110, 85%, 90%)",
        "hsl(120, 85%, 90%)", "hsl(130, 85%, 90%)", "hsl(140, 85%, 90%)", "hsl(150, 85%, 90%)",
        "hsl(160, 85%, 90%)", "hsl(170, 85%, 90%)", "hsl(180, 85%, 90%)", "hsl(190, 85%, 90%)",
        "hsl(200, 85%, 90%)", "hsl(210, 85%, 90%)", "hsl(220, 85%, 90%)", "hsl(230, 85%, 90%)",
        "hsl(240, 85%, 90%)", "hsl(250, 85%, 90%)", "hsl(260, 85%, 90%)", "hsl(270, 85%, 90%)",
        "hsl(280, 85%, 90%)", "hsl(290, 85%, 90%)", "hsl(300, 85%, 90%)", "hsl(310, 85%, 90%)",
        "hsl(320, 85%, 90%)", "hsl(330, 85%, 90%)", "hsl(340, 85%, 90%)", "hsl(350, 85%, 90%)",
        # Varied Saturation/Lightness for contrast
        "hsl(15, 60%, 85%)", "hsl(45, 60%, 85%)", "hsl(75, 60%, 85%)", "hsl(105, 60%, 85%)",
        "hsl(135, 60%, 85%)", "hsl(165, 60%, 85%)", "hsl(195, 60%, 85%)", "hsl(225, 60%, 85%)",
        "hsl(255, 60%, 85%)", "hsl(285, 60%, 85%)", "hsl(315, 60%, 85%)", "hsl(345, 60%, 85%)",
        "hsl(0, 50%, 92%)", "hsl(120, 50%, 92%)", "hsl(240, 50%, 92%)", "hsl(60, 50%, 92%)",
        "hsl(180, 50%, 92%)", "hsl(300, 50%, 92%)", "hsl(30, 50%, 88%)", "hsl(210, 50%, 88%)"
    ]

    def get_color(text):
        import hashlib
        # Use SHA256 for better distribution than MD5
        hash_val = int(hashlib.sha256(text.encode('utf-8')).hexdigest(), 16)
        return PALETTE[hash_val % len(PALETTE)]

    # --- LANE ASSIGNMENT (COLUMN FIX) ---
    # day -> event_id (row object id) -> lane_index
    event_lanes = {} 
    day_max_lanes = defaultdict(int)

    for day in days:
        # Get all unique events for this day
        # Flatten the day_slot_events for this day to get unique rows
        unique_events = []
        seen_ids = set()
        
        # Collect all events happening today
        for slot_idx in range(len(config['time_slots'])):
            for row in day_slot_events[day][slot_idx]:
                rid = id(row)
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    unique_events.append(row)
        
        # Sort by Start Time (using slot index)
        def get_start_slot(r):
            if r['Hora Inicio'] in slot_map:
                return slot_map[r['Hora Inicio']]
            return 0
        
        unique_events.sort(key=lambda x: (get_start_slot(x), x['Grupo']))
        
        # Greedy Interval Packing
        lanes = [] # stores end_slot_index of the last event in each lane
        
        for event in unique_events:
            start_slot = get_start_slot(event)
            # Duration
            end_time = event['Hora Fin']
            duration = 0
            curr = start_slot
            while curr < len(config['time_slots']):
                s_end = config['time_slots'][curr].split('-')[1]
                duration += 1
                if s_end == end_time: break
                curr += 1
            end_slot = start_slot + duration
            
            # Find a lane
            assigned_lane = -1
            for l_idx, lane_end in enumerate(lanes):
                if start_slot >= lane_end:
                    lanes[l_idx] = end_slot
                    assigned_lane = l_idx
                    break
            
            if assigned_lane == -1:
                lanes.append(end_slot)
                assigned_lane = len(lanes) - 1
            
            event_lanes[id(event)] = assigned_lane
            
        day_max_lanes[day] = len(lanes) if lanes else 1

    # HTML Generation
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Horario Ciclo {cycle_num}</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; }}
            h1 {{ text-align: center; color: #333; }}
            table {{ border-collapse: collapse; width: 100%; table-layout: fixed; box-shadow: 0 0 20px rgba(0,0,0,0.1); }}
            th, td {{ border: 1px solid #ccc; padding: 4px; text-align: center; vertical-align: middle; font-size: 0.85em; overflow: hidden; }}
            th {{ background-color: #2196f3; color: white; text-transform: uppercase; height: 40px; }}
            .slot-time {{ font-weight: bold; color: #555; background: #f9f9f9; width: 80px; }}
            .break {{ background-color: #fff3e0; color: #e65100; font-weight: bold; height: 30px; }}
        </style>
    </head>
    <body>
        <h1>Horario Ciclo {cycle_num}</h1>
        <table>
            <thead>
                <tr>
                    <th style="width: 80px;">Hora</th>
    """
    
    for day in days:
        cols = day_max_lanes[day]
        html += f"<th colspan='{cols}'>{day}</th>"
    html += "</tr></thead><tbody>"

    for i, slot in enumerate(config['time_slots']):
        if i in config.get('break_slots', []):
             total_cols = sum(day_max_lanes.values()) + 1
             html += f"<tr class='break'><td class='slot-time'>{slot}</td><td colspan='{total_cols - 1}'>REFRIGERIO</td></tr>"
             continue

        html += f"<tr><td class='slot-time'>{slot}</td>"
        
        for day in days:
            events_in_slot = day_slot_events[day][i]
            max_day_cols = day_max_lanes[day]
            
            # Optimization: If only 1 event and it wants to span (e.g. Theory for whole group)
            # We can check if it effectively "owns" all lanes or if we just want to force it.
            # But adhering to lanes is safer for consistency. 
            # However, user liked the merged look for theory.
            
            # Simple heuristic: If there is ONLY 1 event in this slot AND max_day_cols > 1
            # AND this event is NOT a split section (based on -A, -B suffix convention or just solely occupying)
            # We check if it truly conflicts with nothing else in this slot (already true as len=1).
            # We can define a "Full Width" override.
            
            single_event_override = False
            if len(events_in_slot) == 1 and max_day_cols > 1:
                 e = events_in_slot[0]
                 g_id = e['Grupo']
                 # Heuristic: If it does NOT look like a subgroup Section A/B
                 is_section = g_id.endswith('-A') or g_id.endswith('-B') or g_id.endswith('-C')
                 if not is_section:
                     single_event_override = True
                     prof_name = e['Profesor']
                     bg_color = get_color(prof_name)
                     html += f"<td colspan='{max_day_cols}' style='background-color: {bg_color}'>"
                     html += f"<strong>{e['Curso']}</strong><br>{e['Grupo']}<br>{prof_name}<br>{e['Aula']}"
                     html += "</td>"

            if not single_event_override:
                # Render by Lane
                # Create a map of lane -> event for this slot
                lane_map = {}
                for e in events_in_slot:
                    l_idx = event_lanes.get(id(e), 0)
                    lane_map[l_idx] = e
                
                for col_idx in range(max_day_cols):
                    if col_idx in lane_map:
                        e = lane_map[col_idx]
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
