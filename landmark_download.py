import os
import json
import requests
import re
from urllib.parse import quote
from time import sleep

# ----------------------
# 1. Your landmark data (paste the full JSON here)
# ----------------------
LANDMARKS_JSON = """
{
  "street": "Pushkinskaya Street (Пушкинская улица)",
  "city": "Rostov-on-Don, Russia",
  "length_km": 3.45,
  "note": "Non-military historical buildings and monuments only.",
  "landmarks": [
    {"id":"pushkin_monument","name":"Monument to Alexander Pushkin","name_ru":"Памятник А.С. Пушкину","address":"Pushkinskaya ul. / Voroshilovsky Ave.","year_built":1959,"type":"Monument","style":"Soviet Realism","architect":"G.A. Schultz, M.A. Minkus","description":"...","fun_fact":"...","angles":["front","left_side","right_side","pedestal_detail","wide_boulevard"]},
    {"id":"kirov_monument","name":"Monument to S.M. Kirov","name_ru":"Памятник С.М. Кирову","address":"Kirovskoye Ave. / Pushkinskaya ul.","year_built":1939,"type":"Monument","style":"Soviet Brutalism","architect":"Unknown","description":"...","fun_fact":"...","angles":["front_low","from_plaza","upper_relief_detail","side_view","night"]},
    {"id":"chekhov_monument","name":"Monument to Anton Chekhov","name_ru":"Памятник А.П. Чехову","address":"Pushkinskaya ul. / Chekhov Ave.","year_built":1960,"type":"Monument","style":"Soviet Realism","architect":"Unknown","description":"...","fun_fact":"...","angles":["front","three_quarter","pedestal","avenue_context"]},
    {"id":"vysotsky_monument","name":"Monument to Vladimir Vysotsky","name_ru":"Памятник В.С. Высоцкому","address":"Pushkinskaya ul.","year_built":1995,"type":"Monument","style":"Contemporary","architect":"Unknown","description":"...","fun_fact":"...","angles":["front","side","detail","boulevard_context"]},
    {"id":"pushkin_spheres","name":"Pushkin Decorative Spheres","name_ru":"Пушкинские шары","address":"Pushkinskaya ul. (along the boulevard)","year_built":2000,"type":"Street Art","style":"Contemporary","architect":"Unknown","description":"...","fun_fact":"...","angles":["single_sphere_detail","row_of_spheres","night_illuminated","bas_relief_closeup"]},
    {"id":"lyre_fountain","name":"Lyre Fountain","name_ru":"Фонтан Лира","address":"Pushkinskaya ul. / Nakhichevansky Ave.","year_built":1990,"type":"Fountain","style":"Contemporary","architect":"Unknown","description":"...","fun_fact":"...","angles":["front","lyre_detail","water_jets","evening_lights"]},
    {"id":"library_fountain","name":"Library Fountain","name_ru":"Фонтан у библиотеки","address":"Pushkinskaya ul., 175a","year_built":1990,"type":"Fountain","style":"Contemporary","architect":"Unknown","description":"...","fun_fact":"...","angles":["daytime","evening_lights","water_jets","library_backdrop"]},
    {"id":"don_state_library","name":"Don State Public Library","name_ru":"Донская государственная публичная библиотека","address":"Pushkinskaya ul., 175a","year_built":1886,"type":"Institutional Building","style":"Soviet Modernism","architect":"Unknown","description":"...","fun_fact":"...","angles":["main_facade","tower","entrance","interior_garden","aerial"]},
    {"id":"museum_fine_arts","name":"Rostov Regional Museum of Fine Arts","name_ru":"Ростовский областной музей изобразительных искусств","address":"Pushkinskaya ul., 115","year_built":1898,"type":"Mansion / Museum","style":"Baroque-Classical-Renaissance eclectic","architect":"N.A. Doroshenko","description":"...","fun_fact":"...","angles":["main_facade","entrance_portal","side_wing","detail_ornamentation","courtyard"]},
    {"id":"paramonov_mansion_sfeu","name":"Paramonov Mansion (SFedU Library)","name_ru":"Особняк Парамонова (Библиотека ЮФУ)","address":"Pushkinskaya ul., 148","year_built":1914,"type":"Mansion / University Library","style":"Neoclassical","architect":"L.F. Eberg","description":"...","fun_fact":"...","angles":["front_colonnade","ionic_columns_detail","entrance","side_facade","wide_street_view"]},
    {"id":"kramer_mansion","name":"Mansion of Pavel Kramer","name_ru":"Особняк П. Крамера","address":"Pushkinskaya ul., 114","year_built":1910,"type":"Merchant Mansion","style":"Neoclassical / Art Nouveau","architect":"Unknown","description":"...","fun_fact":"...","angles":["facade","entrance","decorative_detail","street_context"]},
    {"id":"kramer_revenue_house","name":"Revenue House of Pavel Kramer","name_ru":"Доходный дом П. Крамера","address":"Pushkinskaya ul., 116","year_built":1905,"type":"Revenue House","style":"Eclectic","architect":"Unknown","description":"...","fun_fact":"...","angles":["facade","balconies","street_view","ornament_detail"]},
    {"id":"spielrein_mansion","name":"Spielrein Mansion","name_ru":"Особняк Шпильрейн","address":"Pushkinskaya ul., 83","year_built":1897,"type":"Merchant Mansion","style":"Late 19th Century Eclectic","architect":"Unknown","description":"...","fun_fact":"...","angles":["facade","entrance","upper_floors","street_context"]},
    {"id":"zvorykin_house","name":"Ivan Zvorykin House","name_ru":"Дом И.Н. Зворыкина","address":"Pushkinskaya ul., 89 / Semashko Lane, 57","year_built":1914,"type":"Historic Residence","style":"Art Nouveau","architect":"Vasily Popov","description":"...","fun_fact":"...","angles":["corner_view","art_nouveau_facade","iron_grille_detail","main_entrance"]},
    {"id":"gavala_house","name":"Gavala Residential House","name_ru":"Жилой дом Гавала","address":"Pushkinskaya ul., 93","year_built":1895,"type":"Historic Residence","style":"Eclectic","architect":"Unknown","description":"...","fun_fact":"...","angles":["facade","entrance","upper_floors_detail"]},
    {"id":"suprunov_mansion","name":"Suprunov Mansion","name_ru":"Особняк Супрунова","address":"Pushkinskaya ul., 79","year_built":1905,"type":"Merchant Mansion","style":"Neoclassical","architect":"Unknown","description":"...","fun_fact":"...","angles":["main_facade","entrance","decorative_elements","street_context"]},
    {"id":"lashch_revenue_house","name":"Lashch Revenue House","name_ru":"Доходный дом А.П. Ливус","address":"Pushkinskaya ul., 75","year_built":1908,"type":"Revenue House","style":"Gothic Revival","architect":"Unknown","description":"...","fun_fact":"...","angles":["gothic_arches_detail","full_facade","brickwork_detail","street_perspective"]},
    {"id":"mnatsakanova_house","name":"Mnatsakanova House","name_ru":"Доходный дом С.Н. Мнацакановой","address":"Pushkinskaya ul., 65","year_built":1913,"type":"Revenue House","style":"Art Nouveau","architect":"Unknown","description":"...","fun_fact":"...","angles":["art_nouveau_facade","wrought_iron_balconies","plaster_detail","entrance"]},
    {"id":"kushnarev_house","name":"Kushnarev Revenue House","name_ru":"Доходный дом В.С. Кушнарева","address":"Pushkinskaya ul., 51","year_built":1903,"type":"Revenue House","style":"Eclectic","architect":"Unknown","description":"...","fun_fact":"...","angles":["facade","balconies","intersection_context","ornament"]},
    {"id":"reznichenko_house","name":"Reznichenko House","name_ru":"Дом К.О. Резниченко","address":"Pushkinskaya ul., 47","year_built":1898,"type":"Merchant Mansion","style":"Neo-Baroque","architect":"Unknown","description":"...","fun_fact":"...","angles":["baroque_facade","stucco_detail","symmetric_composition","entrance"]},
    {"id":"bakulin_house","name":"Bakulin Apartment House","name_ru":"Доходный дом И.Т. Бакулина","address":"Pushkinskaya ul., 13","year_built":1895,"type":"Apartment House","style":"Eclectic / Romanesque","architect":"Unknown","description":"...","fun_fact":"...","angles":["romanesque_facade","arched_windows","full_building","street_level"]},
    {"id":"bostrikiny_house","name":"Bostrikiny House","name_ru":"Доходный дом Бострикиных","address":"Pushkinskaya ul., 106","year_built":1914,"type":"Apartment Building","style":"Art Nouveau","architect":"Unknown","description":"...","fun_fact":"...","angles":["art_nouveau_attic","facade","modern_signage_contrast","ornament_detail"]},
    {"id":"literary_figures_house","name":"House of Literary Figures","name_ru":"Дом литераторов","address":"Pushkinskaya ul., 78","year_built":1960,"type":"Historic Residence","style":"Soviet","architect":"Unknown","description":"...","fun_fact":"...","angles":["memorial_plaque","facade","full_building","street_context"]},
    {"id":"annunciation_church","name":"Greek Church of the Annunciation","name_ru":"Греческая церковь Благовещения","address":"Pushkinskaya ul.","year_built":1909,"type":"Religious Building","style":"Neo-Byzantine","architect":"Unknown","description":"...","fun_fact":"...","angles":["main_dome","bell_tower","entrance_parvis","full_facade","surrounding_context"]},
    {"id":"rostov_medical_university","name":"Rostov State Medical University Building","name_ru":"Здание Ростовского медицинского университета","address":"Pushkinskaya ul.","year_built":1930,"type":"University Building","style":"Soviet Constructivism","architect":"Unknown","description":"...","fun_fact":"...","angles":["main_facade","entrance","building_sign","street_context"]},
    {"id":"sfeu_library","name":"SFedU Library Mansion","name_ru":"Библиотека ЮФУ","address":"Pushkinskaya ul.","year_built":1900,"type":"University Library / Mansion","style":"Neoclassical","architect":"Unknown","description":"...","fun_fact":"...","angles":["mansion_facade","entrance","library_sign","architectural_detail"]},
    {"id":"memorial_nazi_victims","name":"Memorial to Nazi Victims 1943","name_ru":"Мемориал жертвам нацистской оккупации","address":"Pushkinskaya ul., 175a (library grounds)","year_built":1960,"type":"Memorial","style":"Soviet Memorial","architect":"Unknown","description":"...","fun_fact":"...","angles":["memorial_plaque","full_memorial","library_context","floral_tributes"]},
    {"id":"budyonny_bust","name":"Bust of Semyon Budyonny","name_ru":"Бюст С.М. Будённого","address":"Pushkinskaya ul.","year_built":1950,"type":"Monument / Bust","style":"Soviet Realism","architect":"Unknown","description":"...","fun_fact":"...","angles":["front","three_quarter","pedestal_inscription","boulevard_context"]},
    {"id":"sholokhov_monument","name":"Monument to Mikhail Sholokhov","name_ru":"Памятник М.А. Шолохову","address":"Pushkinskaya ul.","year_built":1985,"type":"Monument","style":"Soviet Realism","architect":"Unknown","description":"...","fun_fact":"...","angles":["front","side","pedestal","boulevard_context"]},
    {"id":"lanterns_1904","name":"Historic Boulevard Lanterns","name_ru":"Исторические фонари бульвара","address":"Pushkinskaya ul. (entire boulevard)","year_built":1904,"type":"Urban Heritage Feature","style":"Historic Revival","architect":"City of Rostov-on-Don","description":"...","fun_fact":"...","angles":["single_lantern_detail","row_of_lanterns","night_illumination","lantern_against_building"]},
    {"id":"gorky_park_gate","name":"Gorky Park Historic Entrance Gate","name_ru":"Ворота Горьковского парка","address":"Pushkinskaya ul. (park boundary)","year_built":1893,"type":"Park Gate","style":"Historicism","architect":"N.A. Doroshenko","description":"...","fun_fact":"...","angles":["gate_facade","fence_detail","park_entrance","context_view"]},
    {"id":"cathedral_nativity","name":"Cathedral of the Nativity of the Virgin Mary","name_ru":"Собор Рождества Пресвятой Богородицы","address":"Near Pushkinskaya ul.","year_built":1860,"type":"Cathedral","style":"Russian-Byzantine","architect":"Konstantin Ton","description":"...","fun_fact":"...","angles":["five_domes","main_facade","entrance_portal","side_apse","aerial"]},
    {"id":"gorky_theater","name":"Maxim Gorky Academic Drama Theater","name_ru":"Академический театр драмы им. М. Горького","address":"Teatralnaya Ploshchad, 1","year_built":1935,"type":"Theater","style":"Soviet Constructivism","architect":"V. Shchuko, V. Gelfreikh","description":"...","fun_fact":"...","angles":["tractor_facade","main_entrance","side_view","aerial","theater_square_context"]},
    {"id":"gorky_theater_fountain","name":"Gorky Theater Square Fountain","name_ru":"Фонтан на Театральной площади","address":"Teatralnaya Ploshchad","year_built":1936,"type":"Fountain","style":"Soviet","architect":"E. Vutechich","description":"...","fun_fact":"...","angles":["full_fountain","giant_figures_detail","turtle_frog_detail","theater_backdrop"]},
    {"id":"underground_mosaics","name":"Underground Passage Mosaics","name_ru":"Мозаики подземных переходов","address":"Major intersections along Pushkinskaya ul.","year_built":1984,"type":"Public Art","style":"Soviet Mosaic Art","architect":"Yuri Palshintsev","description":"...","fun_fact":"...","angles":["full_mosaic_panel","detail_sections","tunnel_view","evening_light"]},
    {"id":"musical_theater","name":"Rostov Musical Theater","name_ru":"Ростовский музыкальный театр","address":"Bolshaya Sadovaya ul., 134","year_built":1999,"type":"Theater","style":"Contemporary","architect":"Unknown","description":"...","fun_fact":"...","angles":["piano_facade","main_entrance","side_view","evening_lit"]},
    {"id":"vorozhein_house","name":"Vorozhein Two-Story House","name_ru":"Двухэтажный дом К.А. Ворожеина","address":"Pushkinskaya ul.","year_built":1900,"type":"Historic Residence","style":"Eclectic","architect":"N.A. Doroshenko","description":"...","fun_fact":"...","angles":["facade","entrance","architectural_detail"]},
    {"id":"green_boulevard","name":"Boulevard Central Promenade (Alley)","name_ru":"Центральная аллея бульвара","address":"Pushkinskaya ul. (3.45 km promenade)","year_built":1885,"type":"Urban Green Heritage","style":"Landscape","architect":"City of Rostov-on-Don","description":"...","fun_fact":"...","angles":["summer_canopy","autumn_colours","central_promenade","tree_lined_perspective"]},
    {"id":"school_49","name":"School No. 49 Historic Building","name_ru":"Историческое здание школы №49","address":"Pushkinskaya ul.","year_built":1910,"type":"Educational Building","style":"Early 20th Century","architect":"Unknown","description":"...","fun_fact":"...","angles":["facade","entrance","full_building","street_context"]},
    {"id":"cinema_house","name":"Cinema House","name_ru":"Дом кино","address":"215, Pushkinskaya St.","year_built":0,"type":"Cinema","style":"","architect":"","description":"...","fun_fact":"...","angles":["facade","entrance","sign"]},
    {"id":"sorge_bust","name":"Bust of Richard Sorge","name_ru":"Бюст Рихарда Зорге","address":"190, Pushkinskaya St.","year_built":0,"type":"Monument / Bust","style":"","architect":"","description":"...","fun_fact":"...","angles":["front","side","pedestal"]},
    {"id":"writers_busts","name":"Busts of Sholokhov, Kalinin & Zakrutkin","name_ru":"Бюсты Шолохова, Калинина и Закруткина","address":"Opposite 160, Pushkinskaya St.","year_built":0,"type":"Monument / Bust","style":"","architect":"","description":"...","fun_fact":"...","angles":["group","individual_sholokhov","individual_kalinin","individual_zakrutkin"]},
    {"id":"grinshteyn_revenue_house","name":"Grinshteyn Revenue House","name_ru":"Доходный дом Хаи Шлемовны Гринштейн","address":"132/59, Pushkinskaya St.","year_built":1897,"type":"Revenue House","style":"Eclectic","architect":"","description":"...","fun_fact":"...","angles":["facade","entrance","ornament"]},
    {"id":"tkachenko_revenue_house","name":"Tkachenko Revenue House","name_ru":"Доходный дом А.А. Ткаченко","address":"34, Pushkinskaya St.","year_built":0,"type":"Revenue House","style":"","architect":"","description":"...","fun_fact":"...","angles":["facade","entrance"]},
    {"id":"sculpture_squirrel","name":"Sculpture Squirrel","name_ru":"Скульптура Белка","address":"Near Pushkinskaya and Gazetny Lane","year_built":2023,"type":"Sculpture","style":"Contemporary","architect":"","description":"...","fun_fact":"...","angles":["front","side","closeup"]},
    {"id":"pushkin_fairytale_sculptures","name":"Pushkin Fairytale Wooden Sculptures","name_ru":"Деревянные скульптуры по сказкам Пушкина","address":"Along Pushkinskaya St.","year_built":0,"type":"Sculpture","style":"Contemporary","architect":"","description":"...","fun_fact":"...","angles":["old_man_fish","golden_cockerel","firebird","cat_scientist"]}
  ]
}
"""

# ----------------------
# 2. Pre‑defined image URLs (the ones we already found)
# ----------------------
PREDEFINED_URLS = {
    "pushkin_monument": [
        "https://upload.wikimedia.org/wikipedia/commons/3/3f/%D0%90.%D0%A1.%D0%9F%D1%83%D1%88%D0%BA%D0%B8%D0%BD_%D0%BD%D0%B0_%D0%9F%D1%83%D1%88%D0%BA%D0%B8%D0%BD%D1%81%D0%BA%D0%BE%D0%B9.JPG",
        "https://upload.wikimedia.org/wikipedia/commons/7/70/Monument_to_Pushkin_%28Rostov-on-Don%29._Sculptor_Gavriil_Schultz_%281959%29.jpg"
    ],
    "kirov_monument": [
        "https://upload.wikimedia.org/wikivoyage/ru/a/a3/Monument_to_Kirov_in_Rostov-on-Don.jpg"
    ],
    "vysotsky_monument": [
        "https://ru.m.wikipedia.org/wiki/%D0%A4%D0%B0%D0%B9%D0%BB:RND-V_Visotsky-Memo.jpg"
    ],
    "budyonny_bust": [
        "https://upload.wikimedia.org/wikipedia/commons/9/90/%D0%9F%D0%B0%D0%BC%D1%8F%D1%82%D0%BD%D0%B8%D0%BA_%28_%D0%91%D1%8E%D1%81%D1%82%29_%D0%A1.%D0%9C.%D0%91%D1%83%D0%B4%D0%B5%D0%BD%D0%BD%D0%BE%D0%B3%D0%BE_%D0%B2_%D0%B3.%D0%A0%D0%BE%D1%81%D1%82%D0%BE%D0%B2%D0%B5-%D0%BD%D0%B0-%D0%94%D0%BE%D0%BD%D1%83.JPG"
    ],
    "gorky_theater_fountain": [
        "https://upload.wikimedia.org/wikipedia/commons/7/7b/Fountain_Rostov_on_Don1.jpg"
    ],
    "zvorykin_house": [
        "https://upload.wikimedia.org/wikipedia/commons/d/dd/%D0%94%D0%BE%D0%BC_%D0%B3%D1%80%D0%B0%D0%B4%D0%BE%D0%BD%D0%B0%D1%87%D0%B0%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA%D0%B0_%D0%98_%D0%9D_%D0%97%D0%B2%D0%BE%D1%80%D1%8B%D0%BA%D0%B8%D0%BD%D0%B0_DSC00323.JPG"
    ],
    "gavala_house": [
        "https://upload.wikimedia.org/wikipedia/commons/e/ef/Gavala_House_2020.jpg"
    ],
    "kushnarev_house": [
        "https://upload.wikimedia.org/wikipedia/commons/6/6f/%D0%94%D0%94_%D0%92%D0%A1_%D0%9F%D1%83%D0%BA%D1%88%D0%BA%D0%B0%D1%80%D0%B5%D0%B2%D0%B0_-_%D0%9F%D1%83%D1%88%D0%BA%D0%B8%D0%BD%D1%81%D0%BA%D0%B0%D1%8F%2C51_DSCN0239.JPG"
    ],
    "bostrikiny_house": [
        "https://upload.wikimedia.org/wikipedia/commons/f/f5/%D0%93.%D0%A0%D0%BE%D1%81%D1%82%D0%BE%D0%B2-%D0%BD%D0%B0-%D0%94%D0%BE%D0%BD%D1%83%2C_%D1%83%D0%BB.%D0%9F%D1%83%D1%88%D0%BA%D0%B8%D0%BD%D1%81%D0%BA%D0%B0%D1%8F%2C_108.JPG"
    ],
    "gorky_theater": [
        "https://upload.wikimedia.org/wikipedia/commons/9/98/%D0%A2%D0%B5%D0%B0%D1%82%D1%80_%D0%93%D0%BE%D1%80%D1%8C%D0%BA%D0%BE%D0%B3%D0%BE_%D0%BD%D0%BE%D1%87%D1%8C%D1%8E.JPG",
        "https://upload.wikimedia.org/wikipedia/commons/0/00/Teatr_Gorkogo.jpg"
    ],
    "musical_theater": [
        "https://upload.wikimedia.org/wikipedia/commons/c/cd/Rostov-on-Don%2C_State_Musical_Theater_%28Opera_House%29%2C_Russia.jpg"
    ],
    "gorky_park_gate": [
        "https://upload.wikimedia.org/wikipedia/commons/5/5c/Rostov_Gorky_Park_2.jpg"
    ]
}

# ----------------------
# 3. Helper: download a single image
# ----------------------
def download_image(url, save_path):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(r.content)
        print(f"  Downloaded: {os.path.basename(save_path)}")
        return True
    except Exception as e:
        print(f"  Failed to download {url}: {e}")
        return False

# ----------------------
# 4. Search Wikimedia Commons for images
# ----------------------
def search_commons(query, max_results=3):
    """
    Search Commons for images with the given query.
    Returns a list of direct image URLs.
    """
    search_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": 6,  # file namespace
        "srlimit": max_results * 3,  # get more to compensate for non‑image files
        "format": "json",
        "origin": "*"
    }
    try:
        resp = requests.get(search_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        titles = [page['title'] for page in data['query']['search'] if 'File:' in page['title']]
        if not titles:
            return []
        
        # Get image info to obtain direct download URLs
        params2 = {
            "action": "query",
            "titles": "|".join(titles[:max_results * 2]),
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
            "origin": "*"
        }
        resp2 = requests.get(search_url, params=params2, timeout=10)
        resp2.raise_for_status()
        data2 = resp2.json()
        
        urls = []
        for page in data2['query']['pages'].values():
            if 'imageinfo' in page:
                for info in page['imageinfo']:
                    if 'url' in info:
                        # Filter for .jpg/.jpeg/.png to avoid PDFs etc.
                        if any(info['url'].lower().endswith(ext) for ext in ['.jpg','.jpeg','.png']):
                            urls.append(info['url'])
                            if len(urls) >= max_results:
                                return urls
        return urls
    except Exception as e:
        print(f"  Commons search error for '{query}': {e}")
        return []

# ----------------------
# 5. Main processing
# ----------------------
def main():
    # Load the landmarks
    data = json.loads(LANDMARKS_JSON)
    landmarks = data['landmarks']
    
    # Create base directory
    base_dir = "pushkinskaya_images"
    os.makedirs(base_dir, exist_ok=True)
    
    for lm in landmarks:
        lm_id = lm['id']
        name = lm.get('name', '')
        name_ru = lm.get('name_ru', '')
        angles = lm.get('angles', [])
        
        print(f"\nProcessing: {name} ({lm_id})")
        
        # Create folder for this landmark
        lm_dir = os.path.join(base_dir, lm_id)
        os.makedirs(lm_dir, exist_ok=True)
        
        downloaded = 0
        
        # 1. Download from pre‑defined URLs
        if lm_id in PREDEFINED_URLS:
            for idx, url in enumerate(PREDEFINED_URLS[lm_id]):
                if not url:
                    continue
                # Use angle name if available, else index
                angle_name = angles[idx] if idx < len(angles) else f"angle_{idx+1}"
                # Clean filename
                angle_name = re.sub(r'[^a-zA-Z0-9_-]', '_', angle_name)
                ext = os.path.splitext(url)[1].split('?')[0]  # remove query
                if not ext:
                    ext = '.jpg'  # fallback
                filename = f"{lm_id}_{angle_name}{ext}"
                save_path = os.path.join(lm_dir, filename)
                if download_image(url, save_path):
                    downloaded += 1
                sleep(0.5)  # be polite
        
        # 2. If we haven't got enough, search Commons
        #    We'll try both English and Russian names
        if downloaded < 3:
            search_queries = [name, name_ru]
            for query in search_queries:
                if not query:
                    continue
                print(f"  Searching Commons for: {query}")
                urls = search_commons(query, max_results=5)
                for url in urls:
                    # Check if we already have this URL (avoid duplicates)
                    if url in [url for _, url in PREDEFINED_URLS.get(lm_id, [])]:
                        continue
                    # Determine angle name
                    idx_angle = downloaded
                    angle_name = angles[idx_angle] if idx_angle < len(angles) else f"commons_{downloaded+1}"
                    angle_name = re.sub(r'[^a-zA-Z0-9_-]', '_', angle_name)
                    ext = os.path.splitext(url)[1].split('?')[0]
                    if not ext:
                        ext = '.jpg'
                    filename = f"{lm_id}_{angle_name}{ext}"
                    save_path = os.path.join(lm_dir, filename)
                    if download_image(url, save_path):
                        downloaded += 1
                        if downloaded >= 3:
                            break
                    sleep(0.5)
                if downloaded >= 3:
                    break
        
        if downloaded == 0:
            print(f"  ⚠️ No images downloaded for {lm_id}")

if __name__ == "__main__":
    main()