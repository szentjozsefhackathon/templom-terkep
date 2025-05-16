import requests
from qgis.core import (QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer, QgsPointXY, 
                      QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, 
                      QgsField, QgsMarkerSymbol, QgsTextFormat, QgsTextBufferSettings, QgsPalLayerSettings, 
                      QgsVectorLayerSimpleLabeling, QgsSingleSymbolRenderer)
from qgis.gui import QgsMapCanvas
from PyQt5.QtGui import QColor, QFont

def get_city_coordinates(city_name):
    base_url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "MiserendTerkep/1.0 (voroslaszlo@papima.hu)"}
    params = {"q": city_name, "format": "json", "limit": 1}
    response = requests.get(base_url, params=params, headers=headers)
    if response.status_code == 200 and response.json():
        city_data = response.json()[0]
        return float(city_data["lat"]), float(city_data["lon"])
    print("Nem található ilyen település.")
    return None

def get_nearby_churches(lat, lon):
    url = "http://miserend.hu/api/v4/nearby"
    headers = {"Content-Type": "application/json", "User-Agent": "MiserendTerkep/1.0"}
    response = requests.post(url, json={"lat": lat, "lon": lon}, headers=headers)
    return response.json() if response.status_code == 200 else None

def add_churches_to_map(churches, canvas):
    if not churches or "templomok" not in churches:
        print("Nincsenek közeli templomok.")
        return
    
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    mercator = QgsCoordinateReferenceSystem("EPSG:3857")
    transform = QgsCoordinateTransform(wgs84, mercator, QgsProject.instance())
    
    layer = QgsVectorLayer("Point?crs=EPSG:3857", "Templomok", "memory")
    provider = layer.dataProvider()
    provider.addAttributes([QgsField("Név", 10)])
    layer.updateFields()
    
    features = []
    for templom in churches["templomok"]:
        lat, lon = float(templom["lat"]), float(templom["lon"])
        point = transform.transform(QgsPointXY(lon, lat))
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        feature.setAttributes([templom.get("nev", "Névtelen templom")])
        features.append(feature)
    
    provider.addFeatures(features)
    
    symbol = QgsMarkerSymbol.createSimple({"name": "circle", "color": "blue", "size": "8"})
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    
    labeling = QgsPalLayerSettings()
    labeling.fieldName = "Név"
    labeling.placement = QgsPalLayerSettings.OverPoint
    labeling.enabled = True
    
    text_format = QgsTextFormat()
    text_format.setSize(12)
    text_format.setColor(QColor("black"))
    text_format.setFont(QFont("Arial"))
    buffer = QgsTextBufferSettings()
    buffer.setEnabled(True)
    buffer.setSize(2)
    buffer.setColor(QColor("white"))
    text_format.setBuffer(buffer)
    
    labeling.textFormat = text_format
    layer.setLabeling(QgsVectorLayerSimpleLabeling(labeling))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()
    
    QgsProject.instance().addMapLayer(layer)
    canvas.refresh()

def open_qgis_with_osm(lat, lon, churches):
    qgs = QgsApplication([], False)
    qgs.initQgis()
    
    canvas = QgsMapCanvas()
    canvas.setCanvasColor(QColor("white"))
    
    url = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
    layer = QgsRasterLayer(f"type=xyz&url={url}", "OpenStreetMap", "wms")
    
    if not layer.isValid():
        print("A térkép réteg betöltése sikertelen.")
        return
    
    QgsProject.instance().addMapLayer(layer)
    canvas.setLayers([layer])
    
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    mercator = QgsCoordinateReferenceSystem("EPSG:3857")
    transform = QgsCoordinateTransform(wgs84, mercator, QgsProject.instance())
    transformed_point = transform.transform(QgsPointXY(lon, lat))
    
    canvas.setDestinationCrs(mercator)
    canvas.setExtent(layer.extent())
    canvas.zoomScale(50000)
    canvas.setCenter(transformed_point)
    
    add_churches_to_map(churches, canvas)
    
    project_file = "miserend_project.qgz"
    if QgsProject.instance().write(project_file):
        print(f"A projekt elmentve: {project_file}")
    else:
        print("A projekt mentése nem sikerült.")
    
    canvas.refresh()
    canvas.show()
    qgs.exec_()
    qgs.exitQgis()

if __name__ == "__main__":
    city_name = input("Add meg a település nevét: ")
    coordinates = get_city_coordinates(city_name)
    
    if coordinates:
        print(f"{city_name} középpontjának koordinátái: {coordinates}")
        churches = get_nearby_churches(*coordinates)
        open_qgis_with_osm(*coordinates, churches)

