"""

"""

import csv, os, arcpy, zipfile
from ftplib import FTP
from glob import glob

home= r"\\Mac\Home\DATA\Source\Data\NOAA_2014_FireIslandTiles"

# Downloaded shapefile of tile footprints
# Selected tiles that intersect barrier island polygon
arcpy.MakeTableView_management(tiles_withselection,tiles_table)
# Exported selected features from table as Text File

# Extract URLs
file_tilelist = "Y:\DATA\Working\NOAA_tiles.txt" # CSV file of ftp URLs for desired tiles
with open(file_tilelist, 'rb') as v:
    table = csv.reader(v, delimiter=',')ct
    ct = 0
    for fieldname in table[0]:
        ct = ct+1
        if fieldname == 'URL':
            iURL = ct
            break
    #iURL = find(table[0]
    tileURLlist = list()
    for tile in table:
        tileURLlist.append(tile[2])
    tileURLlist = tileURLlist[1:]

ftpdirname = os.path.dirname(tileURLlist[0])
hostname = ftpdirname[6:18]
dirpath = ftpdirname[19:]

# Download from FTP
URLlist = tileURLlist[4:]
localfnames = list()
for url in URLlist:
    ftp = FTP(url[6:18]) # connect to host, default port
    ftp.login()                 # user anonymous, passwd anonymous@
    ftp.cwd(os.path.dirname(url)[19:])            # change into source directory
    tilename = os.path.basename(url)
    localfname = '{}\{}'.format(home,tilename)
    ftp.retrbinary('RETR {}'.format(tilename), open(localfname, 'wb').write) # retrieve image and write in local file
    ftp.quit()
    localfnames.append(localfname)

# Merge tiles in Arc, __ at a time
arcpy.MosaicToNewRaster_management(localfnames,home,"NOAA2014_FireIsland", number_of_bands=4)
