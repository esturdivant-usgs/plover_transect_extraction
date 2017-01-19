

import sys
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
#from TransectExtraction import *
from TE_config_Forsythe2014 import *

transects_final
trans_buff
beachwidth_rst = "{site}{year}_bwidth"
cellsize_rst
arcpy.Buffer_analysis(transects_final, trans_buff, "25 METERS", line_end_type="FLAT", dissolve_option="LIST", dissolve_field=['sort_ID', 'beachWidth_MHW'])
arcpy.PolygonToRaster_conversion(trans_buff, 'beachWidth_MHW', beachwidth_rst, cell_assignment='CELL_CENTER', cellsize=cellsize_rst) # cell_center produces gaps only when there is a gap in the features. Max combined area created more gaps.
