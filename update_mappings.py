import json
import os

def update_mappings():
    base_path = os.path.dirname(os.path.abspath(__file__))
    cursos_path = os.path.join(base_path, 'data', 'cursos.json')
    
    mappings = {
        "1": ["DOC001"],
        "2": ["DOC002", "DOC003"],
        "3": ["DOC004"],
        "4": ["DOC005"],
        "5": ["DOC006"],
        "6": ["DOC007"],
        "7": ["DOC009"],
        "8": ["DOC004"],
        "9": ["DOC012"],
        "10": ["DOC008"],
        "11": ["DOC011"],
        "12": ["DOC010"],
        "13": ["DOC013"],
        "14": ["DOC016"],
        "15": ["DOC008"],
        "16": ["DOC014"],
        "17": ["DOC014", "DOC035"],
        "18": ["DOC006"],
        "19": ["DOC015", "DOC036"],
        "20": ["DOC021", "DOC023"],
        "21": ["DOC002", "DOC018"],
        "22": ["DOC002", "DOC019"],
        "23": ["DOC024"],
        "24": ["DOC017", "DOC020", "DOC025"],
        "25": ["DOC003", "DOC022"],
        "26": ["DOC027", "DOC029", "DOC031"],
        "27": ["DOC028", "DOC036"],
        "28": ["DOC019", "DOC023"],
        "29": ["DOC026"],
        "30": ["DOC025", "DOC035"],
        "31": ["DOC030"],
        "32": ["DOC032"],
        "33": ["DOC020"],
        "34": ["DOC022", "DOC033", "DOC034"],
        "35": ["DOC035"],
        "36": ["DOC031"]
    }

    with open(cursos_path, 'r', encoding='utf-8') as f:
        cursos = json.load(f)

    for curso in cursos:
        curso_id = curso['id']
        if curso_id in mappings:
            curso['profesores_ids'] = mappings[curso_id]
        else:
            print(f"Warning: No mapping found for course {curso_id}")

    with open(cursos_path, 'w', encoding='utf-8') as f:
        json.dump(cursos, f, indent=2, ensure_ascii=False)
    
    print("Cursos updated successfully.")

if __name__ == "__main__":
    update_mappings()
