from math import hypot

def CalcBeachWidth_v2(MLW,d_x,d_y,b_slope,sl_x,sl_y): # Calculate beach width (flat distance from MLW to top of beach)
    # Use dune and shoreline projected XY (meters), beach slope, and MLW adjustment value

    # 1 Calculate flat distance between MHW and MLW based on slope and MLW adjustment
    MLWdist = MLW/b_slope
    # 2 Find coordinates of MLW based on transect azimuth and MLWdist
    dx = d_x - sl_x
    dy = d_y - sl_y
    linelen = hypot(dx, dy)
    mlw_x = d_x + dx/linelen * MLWdist
    mlw_y = d_y + dy/linelen * MLWdist

    # 3 Calculate beach width from MLW to dune (top of beach)
    dx = mlw_x - d_x
    dy = mlw_y - d_y
    dMLW = hypot(dx, dy)
    beachWidth_MLW = dMLW

    return [mlw_x, mlw_y, beachWidth_MLW]