def CalcBeachWidthGeometry(MLW,dune_lon,dune_lat,beach_z,beach_slope,SL_Lon,SL_Lat):
    # Calculate beach width based on dune and shoreline coordinates, beach height and slope, and MLW adjustment value
    try:
        beach_h_MLW = beach_z - MLW
        delta_xm_MLW = abs(beach_h_MLW/beach_slope) # Euclidean distance between dune and MLW # Bslope replaces sin of slope # Bslope was pulled in from shoreline points

        # 3 Convert chord distance to Angular distance along great circle (gc)
        mlwKM = delta_xm_MLW/1000
        r = 6371 # Radius of earth in meters
        delta_x_gc_MLW = d2 = 2 * asin(mlwKM/(2*r))

        # 4 Find Azimuth between dune and MHW shoreline
        dlon = radians(SL_Lon - dune_lon)
        dlat = radians(SL_Lat - dune_lat)
        lon1 = radians(dune_lon)
        lat1 = radians(dune_lat)
        lon2 = radians(SL_Lon)
        lat2 = radians(SL_Lat)

        x = sin(dlon) * cos(lat2)
        y = (cos(lat1) * sin(lat2)) - (sin(lat1) * cos(lat2) * cos(dlon))
        theta = atan2(x,y)
        if degrees(theta) < 0:
            azimuth_SL = degrees(theta)+360
        else:
            azimuth_SL = degrees(theta)
        phiR = radians(azimuth_SL)

        # 5 Calculate Position of MLW shoreline based on azimuth # Replace SL position with MLW position # SL is MHW so MHW is replaced by MLW through complex geometry calculations
        latMLW = lat2 = asin((sin(lat2) * cos(d2)) + (cos(lat2) * sin(d2) * cos(phiR)))
        lonMLW = lon2 = lon2 + atan2(sin(phiR)*sin(d2)*cos(lat2), cos(d2)-sin(lat2)*sin(latMLW))
        MLW_Lat = degrees(latMLW)
        MLW_Lon = degrees(lonMLW)

        # 6 Calculate beach width from dune to MLW shoreline
        dlon = radians(MLW_Lon - dune_lon)
        dlat = radians(MLW_Lat - dune_lat)
        a = (sin(dlat/2) * sin(dlat/2)) + (cos(lat1) * cos(lat2) * (sin(dlon/2) * sin(dlon/2)))
        c = 2 * atan2(sqrt(a), sqrt(1-a)) # Angular distance in radians
        dMLW = r * c  # Distance (m) between dune and MLW
        beachWidth_MLW = dMLW*1000

        output = [beach_h_MLW, delta_xm_MLW, azimuth_SL, MLW_Lat, MLW_Lon, beachWidth_MLW]
    except TypeError:
        output = [None, None, None, None, None, None]
    return output