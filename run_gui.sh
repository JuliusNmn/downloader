#!/bin/bash

# Name of the conda environment
ENV_NAME="downloader_conda_env"

# Check if the conda environment already exists
if conda info --envs | grep -q $ENV_NAME; then
    echo "Environment '$ENV_NAME' already exists."
else
    # Create a new conda environment with Python 3.9
    echo "Creating new environment '$ENV_NAME'..."
    conda create -n $ENV_NAME python=3.9 -y

    # Activate the new environment
    source activate $ENV_NAME

    # Install the packages from requirements.txt
    while IFS= read -r package || [ -n "$package" ]; do
        # Skip comments and empty lines
        if [[ ! $package =~ ^# ]] && [[ -n $package ]]; then
            conda install -n $ENV_NAME $package -y || pip install $package
        fi
    done < requirements.txt

    echo "Environment '$ENV_NAME' created and packages installed."
fi

# Activate the conda environment and run the downloader_gui.py script
echo "Activating environment '$ENV_NAME' and running downloader_gui.py..."
activate $ENV_NAME
python downloader_gui.py
