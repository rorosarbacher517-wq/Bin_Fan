// Google Earth Engine template for DEM and Sentinel-2 static features.
// Prerequisite: upload a tower table asset with columns: tower_id, lat, lon.
// Replace users/your_name/towers with your own asset path.

var towers = ee.FeatureCollection('users/your_name/towers').map(function (f) {
  var point = ee.Geometry.Point([ee.Number(f.get('lon')), ee.Number(f.get('lat'))]);
  return ee.Feature(point, f.toDictionary());
});

var region = towers.geometry().buffer(10000);
var dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation');
var terrain = ee.Terrain.products(dem);

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(region)
  .filterDate('2022-01-01', '2023-12-31')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
  .median();

var ndvi = s2.normalizedDifference(['B8', 'B4']).rename('ndvi');
var ndwi = s2.normalizedDifference(['B3', 'B8']).rename('ndwi');
var ndbi = s2.normalizedDifference(['B11', 'B8']).rename('ndbi');

var stack = dem.rename('elevation_m')
  .addBands(terrain.select('slope').rename('slope_deg'))
  .addBands(terrain.select('aspect').rename('aspect_deg'))
  .addBands(ndvi)
  .addBands(ndwi)
  .addBands(ndbi);

var buffered = towers.map(function (f) {
  return f.buffer(500);
});

var features = stack.reduceRegions({
  collection: buffered,
  reducer: ee.Reducer.mean(),
  scale: 30
});

Export.table.toDrive({
  collection: features,
  description: 'gridweather_tower_static_features',
  fileFormat: 'CSV'
});

