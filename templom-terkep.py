import argparse
import requests
import matplotlib.pyplot as plt
from adjustText import adjust_text
from pick import pick
import contextily as ctx
from typing import List, Tuple, Optional, Dict, Any


def get_city_coordinates(city_name: str) -> Tuple[Optional[float], Optional[float]]:
    base_url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "templom-terkep/1.0"}
    params = {"q": city_name, "format": "json", "limit": 1}
    response = requests.get(base_url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            return lat, lon
    print("Nem található ilyen település.")
    return None, None


def get_nearby_churches(lat: float, lon: float, distance: int, hide_no_mass: bool = False) -> List[Dict[str, Any]]:
    distance += 500
    url = "http://miserend.hu/api/v4/nearby"
    headers = {"Content-Type": "application/json"}
    data = {"lat": lat, "lon": lon, "limit": 100, "whenMass": "sunday"}
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        return list(filter(
            lambda church: church["tavolsag"] <= distance and 
            ((hide_no_mass and len(church["misek"]) > 0) or not hide_no_mass),
            response.json()["templomok"]
        ))
    print(f"Hiba történt az API-hívás során: {response.status_code}")
    return []


def get_city_map(
    output_filename: str,
    churches: List[Dict[str, Any]],
    show_center: bool = False,
    color_map: bool = False,
    mass_scheduling: bool = False
) -> None:
    if not churches:
        print("Nincsenek templomok a megadott tartományban.")
        return

    lats = [church['lat'] for church in churches]
    lons = [church['lon'] for church in churches]

    north, south = max(lats), min(lats)
    east, west = max(lons), min(lons)

    center_lat = (north + south) / 2
    center_lon = (east + west) / 2
    fig, ax = plt.subplots(figsize=(8, 8), frameon=False)

    def on_resize(event: Any) -> None:
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        fig.canvas.draw()

    fig.canvas.mpl_connect("resize_event", on_resize)

    ax.set_adjustable('box')
    ax.set_aspect('equal')
    for spine in ['top', 'right', 'left', 'bottom']:
        ax.spines[spine].set_visible(False)

    fig.subplots_adjust(0, 0, 1, 1, 0, 0)
    fig.tight_layout()
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    source = ctx.providers.CartoDB.Positron if not color_map else ctx.providers.OpenStreetMap.Mapnik
    ctx.add_basemap(ax, source=source, crs='EPSG:4326')

    if show_center:
        ax.scatter(center_lon, center_lat, c='blue', marker='x', s=100, label='Középpont')

    texts = []
    text_objects = []
    for church in churches:
        lon, lat = church['lon'], church['lat']
        name = church.get('nev', 'Ismeretlen templom')
        ax.scatter(lon, lat, c='red', marker='o', s=100, label='Templom')
        mass_sched = "" if not mass_scheduling else f"\n{', '.join([':'.join(mass['idopont'].split(' ')[1].split(':')[:2]) for mass in church['misek']])}"
        mass_sched = mass_sched if mass_sched != "\n" else ""
        text = ax.text(
            lon, lat, f"{name}{mass_sched}",
            fontsize=8, ha='center', va='bottom',
            bbox=dict(facecolor='white', alpha=0.7, edgecolor='black')
        )
        texts.append(text)
        text_objects.append(text)

    adjust_text(
        texts, ax=ax, max_move=(200, 200), time_lim=20,
        arrowprops=dict(arrowstyle="->", color='black'), min_arrow_len=200
    )

    def on_press(event: Any) -> None:
        for text in text_objects:
            if text.contains(event)[0]:
                text.user_data = (event.xdata, event.ydata)
                text.set_bbox(dict(facecolor='yellow', alpha=0.7, edgecolor='black'))
                fig.canvas.draw()
                return

    def on_motion(event: Any) -> None:
        for text in text_objects:
            if hasattr(text, 'user_data') and event.xdata and event.ydata:
                text.set_position((event.xdata, event.ydata))
                fig.canvas.draw()
                return

    def on_release(event: Any) -> None:
        for text in text_objects:
            if hasattr(text, 'user_data'):
                del text.user_data
                text.set_bbox(dict(facecolor='white', alpha=0.7, edgecolor='black'))
                fig.canvas.draw()
                return

    fig.canvas.mpl_connect('button_press_event', on_press)
    fig.canvas.mpl_connect('motion_notify_event', on_motion)
    fig.canvas.mpl_connect('button_release_event', on_release)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_frame_on(False)
    print("A térkép elkészült. A szövegek húzással átrendezhetőek. A végleges elrendezés után zárja be az ablakot")
    plt.box(on=None)
    plt.axis('off')
    plt.show(block=True)
    fig.savefig(output_filename, dpi=300, bbox_inches='tight', pad_inches=0)
    print(f"A térkép elmentve ide: {output_filename}")


def select_churches(churches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    title = "Válassza ki a templomokat: (szóköz a kiválasztáshoz, Enter a folytatáshoz)"
    options = [f"{church.get('nev', 'Ismeretlen templom')} ({church.get('tavolsag','?')} m, {len(church['misek'])} mise)" for church in churches]
    selected = pick(options, title, multiselect=True)
    return [churches[i[1]] for i in selected]


def main() -> None:
    parser = argparse.ArgumentParser(description="Település templomainak térképe")
    parser.add_argument("--city-name", nargs="?", help="A település neve")
    parser.add_argument("--output-filename", nargs="?", help="A kimeneti fájl neve")
    parser.add_argument("--distance", nargs="?", help="Távolság m-ben", type=int)
    parser.add_argument("--show-center", action="store_true", help="A középpont megjelenítése")
    parser.add_argument("--select-churches", action="store_true", help="Templomok kiválasztása")
    parser.add_argument("--color-map", action="store_true", help="Színes térkép")
    parser.add_argument("--mass-scheduling", action="store_true", help="Misek időpontjainak megjelenítése")
    parser.add_argument("--hide-no-mass", action="store_true", help="Nem miséző templomok elrejtése")
    args = parser.parse_args()

    city_name = args.city_name or input("Adja meg a település nevét (Szeged): ") or "Szeged"
    output_filename = args.output_filename or input("Adja meg a kimeneti fájl nevét (terkep.png): ") or "terkep.png"
    distance_input = args.distance or input("Adja meg a távolságot (5000): ") or 5000

    try:
        distance = int(distance_input)
    except ValueError:
        print("A távolságnak egész számnak kell lennie.")
        return

    lat, lon = get_city_coordinates(city_name)
    if lat is None or lon is None:
        return

    churches = get_nearby_churches(lat, lon, distance, hide_no_mass=args.hide_no_mass)
    if args.select_churches:
        churches = select_churches(churches)

    get_city_map(output_filename, churches, show_center=args.show_center, color_map=args.color_map, mass_scheduling=args.mass_scheduling)


if __name__ == "__main__":
    main()