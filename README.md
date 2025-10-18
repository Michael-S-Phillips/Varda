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
- [uv package manager](https://docs.astral.sh/uv/)

## Clone the Repository:

in your terminal, navigate to the directory you want to install the project in, and run the following commands

## Setup Development environment:
1. clone the repository and navigate to the project directory.
2. run the following command to setup the environment and install dependencies:
```bash
uv sync
```

## Run Varda:
```bash
uv run varda
# or...
varda
```