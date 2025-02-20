import geopandas as gpd
import matplotlib.pyplot as plt
from PIL import Image
#import cartopy.crs as ccrs
#import matplotlib.image as mpimg
from shapely.geometry import Polygon, Point
import random
#import shapely.wkt
from shapely.errors import GEOSException

# Загрузка входных данных
def load_geojson(file_path):
    """Загрузка GeoJSON файла."""
    return gpd.read_file(file_path)


# Функция для проверки, находится ли точка в разрешенной зоне
def is_valid_location(point, parcel, min_distance, buildings, restricted_areas):
    """Проверяет, можно ли разместить здание в данной точке."""
    # Проверяем, находится ли точка в пределах участка
    if not parcel.contains(point).any():
        return False

    # Если restricted_areas — это список, переводим его в GeoDataFrame
    if isinstance(restricted_areas, list):
        restricted_areas = gpd.GeoDataFrame(geometry=restricted_areas, crs="EPSG:4326")  # Укажите исходный CRS
    
    # Преобразование CRS для restricted_areas
    restricted_areas = restricted_areas.to_crs(epsg=3395)  # Change EPSG code as needed for your area

    # Проверяем, находится ли точка в запрещенной зоне, итерируясь по столбцу .geometry
    for area in restricted_areas.geometry:
        #print(f"restricted_area: {area}")
        #print(f"point: {point}")
        #print("---")
        if area.contains(point):
            return False

    # Проверяем минимальное расстояние до других зданий
    for b in buildings:
        b_geom = b.geometry if hasattr(b, 'geometry') else b
        if point.distance(b_geom) < min_distance:
            return False
    return True


# Функция для автоматической застройки участка
def auto_build(parcel, density, min_distance, restricted_areas):
    """Автоматическое размещение зданий на участке."""
    print(f"Автоматическая застройка участка ...")

    # перепроецирование в проекционную систему координат (например, UTM)
    parcel = parcel.to_crs(epsg=3395)  # Change EPSG code as needed for your area

    total_area = parcel.geometry.area.sum()
    print(f"total_area: {total_area}")
    buildable_area = total_area * (density / 100)  # Допустимая площадь для застройки
    print(f"Допустимая площадь для застройки: {buildable_area}")

    # Список для хранения расположенных зданий
    buildings = []  

    while buildable_area > 0:
        # Генерация случайной точки внутри границ участка
        x = random.uniform(parcel.total_bounds[0], parcel.total_bounds[2])
        y = random.uniform(parcel.total_bounds[1], parcel.total_bounds[3])
        # Обратное преобразование в географические координаты
        point = Point(x, y)
        #print(f"point: {point}")
    
        # Проверка валидности точки
        if point.is_valid and is_valid_location(point, parcel, min_distance, buildings, restricted_areas):
            buildings.append(point)  # Убедитесь, что добавляете объект Point
            buildable_area -= min_distance**2  # Уменьшаем доступную площадь

    # Преобразование списка точек в GeoDataFrame
    buildings_gdf = gpd.GeoDataFrame(geometry=buildings, crs=parcel.crs)
    buildings_gdf = buildings_gdf.to_crs(epsg=4326)  # Преобразование обратно в географические координаты
    return buildings_gdf  # Возвращаем GeoDataFrame


def visualize_with_background(parcel_file, map_image, density, min_distance, restricted_file):
    """Отображение застройки на карте с подложкой."""
    print(f"Файл границ участка: '{parcel_file}'")
    print(f"Файл карты: '{map_image}'")
    print(f"Файл запрещенных зон: '{restricted_file}'")
    print(f"Плотность застройки: '{density}'")
    print(f"Минимальное расстояние между зданиями: '{min_distance}'")

    # Загрузка данных
    parcel = gpd.read_file(parcel_file)

    # Загрузка запрещенных зон
    restricted_areas = gpd.read_file(restricted_file) if restricted_file else []

    # Вычисление границ данных
    bounds = parcel.total_bounds  # [minx, miny, maxx, maxy]
    print(f"bounds: {bounds}")

    # Координаты верхнего левого угла
    lon_top_left = 107.59363961013395
    lat_top_left = 51.80979610464206

    # Размеры изображения в пикселах
    img_width = 685
    img_height = 561

    # Определение границ (extent) для изображения
    extent = [
        lon_top_left + (50 / img_width)/48,  # x_min (долгота)
        lon_top_left + (bounds[2] - bounds[0]) + (50 / img_width)/48,  # x_max
        lat_top_left - (bounds[3] - bounds[1]),  # y_min
        lat_top_left # y_max (широта)
    ]

    # Создание фигуры и оси
    fig, ax = plt.subplots(figsize=(10, 10))

    # Загрузка изображения карты и разворот на 180 градусов по оси Y
    img = Image.open(map_image)
    #img = img.transpose(Image.FLIP_LEFT_RIGHT)  # Разворот изображения

    # Отображение изображения карты
    ax.imshow(img, extent=extent, aspect='auto')

    # Отображение участков
    parcel.plot(ax=ax, color='lightgrey', edgecolor='black', alpha=0.5)

    # Отображение запрещенных зон
    if not restricted_areas.empty:
        restricted_areas.plot(ax=ax, color='red', edgecolor='black', alpha=0.3)

    # Автоматическая застройка
    buildings = auto_build(parcel, density, min_distance, list(restricted_areas.geometry))
    #print("Вернулись из auto_build() ...")
    #print(f"buildings: {buildings}")
    #print("-"*30)

    # Отображение зданий
    processed_buildings = []
    print("Отображение зданий ...")
    for index, building in buildings.iterrows():  # Use iterrows to get index and row
        #print(f"index: {index}")
        #print(f"building: {building}")
        point = building.geometry  # Access the geometry directly
        #print(f"building: {type(point)} - {point}")  # This will show the Point object
        ax.plot(point.x, point.y, 'bo')  # Now you can access x and y attributes
        processed_buildings.append(point)

    buildings_gdf = gpd.GeoDataFrame(geometry=processed_buildings, crs=parcel.crs)
    print(f"Выходной файл: 'buildings.geojson'")
    buildings_gdf.to_file("buildings.geojson", driver="GeoJSON")

    # Настройка отображения
    ax.set_title('План застройки с подложкой карты')
    ax.set_xlabel('Долгота')
    ax.set_ylabel('Широта')

    # Показать и сохранить результат
    plt.savefig('buildings.png')
    plt.show()
    print(f"Графическое представление застройки сохранено в файле: 'buildings.png'")
    print("-"*30)


def main():
    visualize_with_background(
        parcel_file='input4.geojson',           #  Входные данные - границы участка
        map_image='map.png',                    #  Входные данные - карта
        density=30,                             #  Входные данные - плотность застройки
        min_distance=10,                        #  Входные данные - минимальное расстояние между зданиями
        restricted_file='restricted.geojson'    #  Входные данные - запрещенные зоны
    )

if __name__ == "__main__":
    print("Запуск программы ...")
    main()









