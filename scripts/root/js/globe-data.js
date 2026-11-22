/* RobinLab globe — offline location helpers. Nothing here touches the network.
   tz -> [city, region, country, lat, lon] for common IANA zones (city centroid, approximate). */
(function (w) {
  'use strict';
  var Z = {
    'Asia/Kolkata': ['New Delhi', 'Delhi', 'India', 28.61, 77.21], 'Asia/Calcutta': ['New Delhi', 'Delhi', 'India', 28.61, 77.21],
    'America/New_York': ['New York', 'New York', 'United States', 40.71, -74.01], 'America/Chicago': ['Chicago', 'Illinois', 'United States', 41.88, -87.63],
    'America/Denver': ['Denver', 'Colorado', 'United States', 39.74, -104.99], 'America/Los_Angeles': ['Los Angeles', 'California', 'United States', 34.05, -118.24],
    'America/Phoenix': ['Phoenix', 'Arizona', 'United States', 33.45, -112.07], 'America/Anchorage': ['Anchorage', 'Alaska', 'United States', 61.22, -149.9],
    'Pacific/Honolulu': ['Honolulu', 'Hawaii', 'United States', 21.31, -157.86], 'America/Toronto': ['Toronto', 'Ontario', 'Canada', 43.65, -79.38],
    'America/Vancouver': ['Vancouver', 'British Columbia', 'Canada', 49.28, -123.12], 'America/Mexico_City': ['Mexico City', '', 'Mexico', 19.43, -99.13],
    'America/Sao_Paulo': ['São Paulo', 'São Paulo', 'Brazil', -23.55, -46.63], 'America/Argentina/Buenos_Aires': ['Buenos Aires', '', 'Argentina', -34.6, -58.38],
    'America/Bogota': ['Bogotá', '', 'Colombia', 4.71, -74.07], 'America/Lima': ['Lima', '', 'Peru', -12.05, -77.04], 'America/Santiago': ['Santiago', '', 'Chile', -33.45, -70.67],
    'Europe/London': ['London', 'England', 'United Kingdom', 51.51, -0.13], 'Europe/Dublin': ['Dublin', '', 'Ireland', 53.35, -6.26],
    'Europe/Paris': ['Paris', 'Île-de-France', 'France', 48.86, 2.35], 'Europe/Berlin': ['Berlin', '', 'Germany', 52.52, 13.4],
    'Europe/Madrid': ['Madrid', '', 'Spain', 40.42, -3.7], 'Europe/Rome': ['Rome', 'Lazio', 'Italy', 41.9, 12.5], 'Europe/Amsterdam': ['Amsterdam', '', 'Netherlands', 52.37, 4.9],
    'Europe/Stockholm': ['Stockholm', '', 'Sweden', 59.33, 18.07], 'Europe/Warsaw': ['Warsaw', '', 'Poland', 52.23, 21.01], 'Europe/Istanbul': ['Istanbul', '', 'Türkiye', 41.01, 28.98],
    'Europe/Moscow': ['Moscow', '', 'Russia', 55.76, 37.62], 'Europe/Kyiv': ['Kyiv', '', 'Ukraine', 50.45, 30.52], 'Europe/Kiev': ['Kyiv', '', 'Ukraine', 50.45, 30.52],
    'Africa/Cairo': ['Cairo', '', 'Egypt', 30.04, 31.24], 'Africa/Lagos': ['Lagos', '', 'Nigeria', 6.52, 3.38], 'Africa/Johannesburg': ['Johannesburg', 'Gauteng', 'South Africa', -26.2, 28.05],
    'Africa/Nairobi': ['Nairobi', '', 'Kenya', -1.29, 36.82], 'Asia/Dubai': ['Dubai', '', 'United Arab Emirates', 25.2, 55.27], 'Asia/Riyadh': ['Riyadh', '', 'Saudi Arabia', 24.71, 46.68],
    'Asia/Tehran': ['Tehran', '', 'Iran', 35.69, 51.39], 'Asia/Karachi': ['Karachi', 'Sindh', 'Pakistan', 24.86, 67.01], 'Asia/Dhaka': ['Dhaka', '', 'Bangladesh', 23.81, 90.41],
    'Asia/Kathmandu': ['Kathmandu', '', 'Nepal', 27.72, 85.32], 'Asia/Colombo': ['Colombo', '', 'Sri Lanka', 6.93, 79.86], 'Asia/Bangkok': ['Bangkok', '', 'Thailand', 13.76, 100.5],
    'Asia/Ho_Chi_Minh': ['Ho Chi Minh City', '', 'Vietnam', 10.82, 106.63], 'Asia/Jakarta': ['Jakarta', '', 'Indonesia', -6.21, 106.85], 'Asia/Singapore': ['Singapore', '', 'Singapore', 1.35, 103.82],
    'Asia/Kuala_Lumpur': ['Kuala Lumpur', '', 'Malaysia', 3.14, 101.69], 'Asia/Manila': ['Manila', '', 'Philippines', 14.6, 120.98], 'Asia/Hong_Kong': ['Hong Kong', '', 'China', 22.32, 114.17],
    'Asia/Shanghai': ['Shanghai', '', 'China', 31.23, 121.47], 'Asia/Taipei': ['Taipei', '', 'Taiwan', 25.03, 121.57], 'Asia/Seoul': ['Seoul', '', 'South Korea', 37.57, 126.98],
    'Asia/Tokyo': ['Tokyo', '', 'Japan', 35.68, 139.69], 'Australia/Sydney': ['Sydney', 'New South Wales', 'Australia', -33.87, 151.21], 'Australia/Melbourne': ['Melbourne', 'Victoria', 'Australia', -37.81, 144.96],
    'Australia/Perth': ['Perth', 'Western Australia', 'Australia', -31.95, 115.86], 'Pacific/Auckland': ['Auckland', '', 'New Zealand', -36.85, 174.76]
  };

  /** Approximate city for the browser's IANA zone, or null when the zone is not in the table. */
  function fromTimezone(tz) {
    var z = Z[tz];
    return z ? { city: z[0], region: z[1], country: z[2], lat: z[3], lon: z[4], precise: false } : null;
  }

  /** Sunrise/sunset (NOAA approximation) as Date objects for the given day; null at polar day/night. */
  function sun(lat, lon, date) {
    var rad = Math.PI / 180;
    var start = Date.UTC(date.getFullYear(), 0, 0);
    var n = Math.floor((Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) - start) / 864e5);
    var g = (2 * Math.PI / 365) * (n - 1);
    var eq = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
    var dec = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
    var c = (Math.cos(90.833 * rad) - Math.sin(lat * rad) * Math.sin(dec)) / (Math.cos(lat * rad) * Math.cos(dec));
    if (c > 1 || c < -1) return null;
    var ha = Math.acos(c) / rad;
    var base = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
    return {
      rise: new Date(base + (720 - 4 * (lon + ha) - eq) * 6e4),
      set: new Date(base + (720 - 4 * (lon - ha) - eq) * 6e4)
    };
  }

  w.RLGlobeData = { fromTimezone: fromTimezone, sun: sun };
})(window);
