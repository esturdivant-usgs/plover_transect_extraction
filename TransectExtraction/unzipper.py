# Unzip files from Downloads folder
import zipfile
from glob import glob

indir = r"\\Mac\Home\Downloads"
outdir = r"\\Mac\Home\DATA\Source\Data\Plover\FireIsland2011\NYS2010_FireIsland2"
home = r"\\Mac\Home\Documents\ArcGIS\Default.gdb"

# Unzip *.zip files in indir and save them to outdir
ziplist = glob("{}\\*.zip".format(indir))       #list *zip files in indir
#rlist = list()                                  #initialize list of files
for zpath in ziplist:
    with zipfile.ZipFile(zpath, 'r') as zip_ref:
        zip_ref.extractall(outdir)
    (path,zname) = os.path.split(zpath)
    (fname, ext) = os.path.splitext(zname)
    #rlist.append("{}\\{}.jp2".format(outdir,fname))

# Mosaic images
arcpy.env.workspace = r"\\Mac\Home\DATA\Source\Data\Plover\FireIsland2011\NYS2010_FireIsland3"
rlist = arcpy.ListDatasets('*.jp2')

for i in range(3,8):
    if not len(rlist) % i:
        tilespermosaic = i
    else:
        continue
if not tilespermosaic:
    print 'Tiles do not divide evenly by a number between 3 and 8.'

ct = 0
for i in range(0,len(rlist),tilespermosaic):
    ct = ct+1
    arcpy.MosaicToNewRaster_management(rlist[i:i+tilespermosaic],home,"NYS2010_FireIsland_g{}".format(ct), number_of_bands=4)


c