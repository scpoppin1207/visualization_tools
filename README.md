# Tools for Visualization

This repository contains visualization tools for 3D semantic scene completion and training analysis.

## 🦉 Environment Setup

### Base Environment (renderpy)

Create a base environment for general visualization tasks:

```bash
# Create environment
conda create -n renderpy python=3.9
conda activate renderpy

# Install required packages
pip install matplotlib numpy Pillow seaborn pandas open3d plyfile scipy tqdm mitsuba
```

### Mayavi Environment (mayavi_clean)

Create a dedicated environment for 3D voxel visualization with Mayavi:

```bash
# Create clean environment
conda create -n mayavi_clean python=3.9 -c conda-forge
conda activate mayavi_clean

# Install Mayavi and dependencies
conda install -c conda-forge mayavi
conda install -c conda-forge open3d

# Install additional packages
pip install Pillow
```

---

## 🐦 Testing Your Installation

### Test Mayavi Environment

Validate your Mayavi installation with these tests:

**(a) Test Qt Backend**

```python
from PyQt5.QtWidgets import QApplication, QLabel
import sys
app = QApplication(sys.argv)
label = QLabel("Hello from Qt")
label.show()
app.exec_()
```

**(b) Test TraitsUI**

```python
import os
os.environ["ETS_TOOLKIT"] = "qt"
os.environ["QT_API"] = "pyqt5"

from traits.api import HasTraits, Str
from traitsui.api import View, Item

class Person(HasTraits):
    name = Str() 
    traits_view = View(Item('name')) 
 
p = Person(name="ChatGPT") 
p.configure_traits() 
```

**(c) Test Mayavi**

```python
import os
os.environ["ETS_TOOLKIT"] = "qt"
os.environ["QT_API"] = "pyqt5"

from mayavi import mlab 
mlab.test_plot3d() 
mlab.show()
```

---

## 📦 Demo Data

To test the visualization tools, download example data from OneDrive:

### Quick Links

- **All Data (Recommended)**: [Download All](https://entuedu-my.sharepoint.com/:f:/g/personal/rqian003_e_ntu_edu_sg/IgCoDeLoUMbWRZk4DHfXO4c7Ael43smbSmxBSpn6XioV82c?e=X10Pro)
  - Includes: RGB, Gaussian, and Voxel data

### Individual Downloads

- **Gaussian Data**: [Download](https://entuedu-my.sharepoint.com/:f:/g/personal/rqian003_e_ntu_edu_sg/IgCmYPap26Q4Rp9doN7ltUOWAaRD8i8CUNX0BFGTuMq5iBY?e=ebBs3R)
  - For: `gaussian/vis_gs.sh` and `gaussian/vis_gs_glob.sh`

- **Voxel Data**: [Download](https://entuedu-my.sharepoint.com/:f:/g/personal/rqian003_e_ntu_edu_sg/IgCMAtmuiTjxQLTcar1eP30VAVsUl7msK7pCWHpPQX0FtGM?e=AagyLM)
  - For: `voxels/vis_occ.sh` and `voxels/vis_occ_rot.sh`
  
- **RGB Data**: [Download](https://entuedu-my.sharepoint.com/:f:/g/personal/rqian003_e_ntu_edu_sg/IgBqq-qDMMZzRrZBu89ypDtiAS1oK8aDl65IhW0RIealDnA?e=xSXLLQ)

### Setup Instructions

After downloading, extract the data and update the paths in the scripts:

**For Gaussian visualization:**
```bash
# Edit gaussian/vis_gs.sh or gaussian/vis_gs_glob.sh
PLY_ROOT="/path/to/your/downloaded/data"  # Update this path
PLY_FOLD="vis_occ_da_gaussian_cam"  # Or your data folder name
```

**For Voxel visualization:**
```bash
# Edit voxels/vis_occ.sh
PCD_ROOT="/path/to/your/downloaded/data"  # Update this path
PCD_FOLD="vis_occ_semantic"  # Or your data folder name
```

**Typical structure after extraction:**
```
/path/to/your/downloaded/data/
├── vis_occ_da_gaussian_cam/        # Gaussian data with camera projection
│   ├── scene0000_00/
│   │   ├── pcd_00012.ply
│   │   ├── pcd_00033.ply
│   │   └── pcd_00076.ply
│   └── scene0031_00/
│       └── pcd_00053.ply
|       └── ...
│
├── vis_occ_semantic/               # Voxel occupancy with semantic labels
│   ├── scene0000_00/
│   │   ├── pcd_00012.ply
│   │   ├── pcd_00033.ply
│   │   └── pcd_00076.ply
│   └── scene0031_00/
│       └── pcd_00053.ply
|       └── ... 
│ 
└── rgb_images/                     # RGB images
    └── ...
```

> 💡 **Tip**: The scripts will prompt you if the data path is incorrect. Simply update the `PLY_ROOT` or `PCD_ROOT` variable at the top of each script.

---

## 🦚 Usage

### Training & Efficiency Analysis ([experiment/](experiment/README.md))

Visualize training metrics, efficiency comparisons, and latency analysis.

```bash
cd experiment
conda activate renderpy
bash vis_train.sh      # Training loss & mIoU curves
bash vis_effect.sh     # Efficiency metrics (anchors, features, memory)
bash vis_latency.sh    # Latency and parameter scatter plots
```

**[→ See detailed documentation](experiment/README.md)**

---

### 3D Voxel Visualization ([voxels/](voxels/README.md))

Render static and rotating 3D voxel occupancy with Mayavi.

```bash
cd voxels
conda activate mayavi_clean
bash vis_occ.sh        # Static visualization
bash vis_occ_rot.sh    # Rotating animation + GIF
```

**Quick mode:** Auto-generate with defaults - only select method/scene/frame.

**Interactive desktop viewer:**

```bash
conda activate mayavi_clean
python -m vox_viewer.main
```

**[→ See detailed documentation](voxels/README.md)** · **[Vox Viewer](vox_viewer/README.md)**

---

### Gaussian Splatting ([gaussian/](gaussian/README.md) · [gs_viewer/](gs_viewer/README.md))

**Interactive desktop viewer** (PyQt5 + Mayavi，支持多文件标签页与分屏对比)：

```bash
conda activate mayavi_clean
python -m gs_viewer.main
python -m gs_viewer.main --check
```

High-quality offline Gaussian rendering with Mitsuba or matplotlib:

**Mitsuba (recommended):**
```bash 
conda activate renderpy
bash vis_gs.sh
bash vis_gs_glob.sh
``` 

**Matplotlib (lightweight):**
```bash
cd gaussian/matplotlib
conda activate renderpy
bash vis_gs.sh 
```

**[→ See detailed documentation](gaussian/README.md)** · **[GS Viewer](gs_viewer/README.md)**

---

### Miscellaneous Figures ([pictures/](pictures/README.md))

Utilities for generating paper figures, color bars, and point flow visualizations.

```bash
cd pictures
conda activate renderpy
bash <script_name>.sh 
```

**[→ See detailed documentation](pictures/README.md)**

---

## 📝 Important Notes

> 💡 **When using Mayavi**, you **must set the ETS environment variables** at the beginning of your scripts to ensure it correctly uses the Qt backend:

```python
import os
os.environ['ETS_TOOLKIT'] = 'qt'
os.environ['QT_API'] = 'pyqt5'

# Import other modules after setting environment
import open3d as o3d
import numpy as np
from mayavi import mlab
from pathlib import Path
# ...
```

> ⚠️ **Offscreen Rendering**: The rotation tool uses `xvfb-run` for offscreen rendering. Install if needed:
> ```bash
> sudo apt-get install xvfb
> ```












