# Varda

Varda is a GUI based app that will allow users to visualize and analyze image data (specifially hyper-spectral and multi-spectral data). 
Users can upload an image file and examine regions of interest (ROIs), pixel spectra, and adjust band paramters. We are currently working
on adding more features / support for other types of image data. 

To get started using Varda, follow the guide [here](https://www.notion.so/Getting-Started-17002b238495807588e4c009e9a484dc). 
This guide assumes you use the pip package installer. We may add support for other package installers in the future. 

This app is a work in progress! Users are also encouraged to add their own custom features for their individual workflows. If you are interested
in doing this, [this](https://www.notion.so/Feature-Development-Workflow-17002b23849580649788ff3e4b2adb6f) guide on Vardas code structure may
be useful to you. 


# Getting Started

## Prerequisites:

- Python 3.12+ installed
- Git is installed on your computer, and you have [connected an ssh key to GitHub](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)

## Clone the Repository:

in your terminal, navigate to the directory you want to install the project in, and run the following commands

```bash
   git clone git@github.com:Michael-S-Phillips/Varda.git
   cd Varda
```

## Setup Development environment:

```bash
python -m venv .venv       # Create the virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

pip install -e .                    # This should install runtime dependencies and build the project in editable/development mode
pip install -r requirements-dev.txt # For now, you may have to do this to manually install the development dependencies (pytest, pylint, black...)
```

## Run Varda:

```bash
varda  # this is the command to start the program
```

## Run pytest (unit testing):

```bash
pytest tests/
# or...
pytest
```

## Run Pylint (static code analyzer):

```bash
pylint src/
```

## Run Black (formatter):

```bash
# to simply check for formatting issues
black --check src/
# To actually apply formatting
black src/
```
