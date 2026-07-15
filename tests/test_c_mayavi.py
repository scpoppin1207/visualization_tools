import os
os.environ["ETS_TOOLKIT"] = "qt"
os.environ["QT_API"] = "pyqt5"

from mayavi import mlab
mlab.test_plot3d()
mlab.show()