# GEE Asset Help

**GEE Asset Help** is a graphical asset management tool built with PySide6 and the Google Earth Engine (GEE) API. It allows users to conveniently browse, refresh, delete, and move GEE folders and datasets, making batch operations on GEE assets easier and more efficient.

> ⚠️ **Note:**  
> When performing **batch uploads of TIF files**, the tool will automatically **merge them into a single multi-band TIF** and save it in the `output` folder.  
> You will then need to **manually upload** this merged TIF to your **GEE Assets** 

### Create and activate environment
```bash
conda create -n your_env=3.11 -y
conda activate your_env
```
## Set the environment variable "PROJECT" to your Google Cloud project ID:
```bash
Windows (Command Prompt or PowerShell):
setx PROJECT "your-project-id" /M 

Linux: 
echo 'export PROJECT="your-project-id"' >> ~/.bashrc
source ~/.bashrc
```
### Install dependencies
Install using uv:
```bash
uv pip install -r requirements.txt
```

Install from PyPI:
```bash
pip install -r requirements.txt
```

Install from conda-forge:
```bash
conda env create -f environment.yml
conda activate gee_asset_env
```

## Run
```bash
python main.py
```
