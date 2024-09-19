import tkinter as tk
from tkinter import filedialog
import spectral
import rasterio as rio
import matplotlib.pyplot as plt
import numpy as np
from skimage import exposure


class SpectralDataViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Spectral Cube Analysis Tool")
        self.data = None
        self.transform = None
        self.default_rgb_bands = (29, 19, 9)  # Example default bands

        # Setup UI
        load_button = tk.Button(root, text="Load Data", command=self.load_data)
        load_button.pack()

    def load_data(self):
        file_path = filedialog.askopenfilename(filetypes=[("ENVI Files", "*.hdr")])
        if file_path:
            # Load spectral data
            self.data = spectral.open_image(file_path)
            self.data = self.data.load()

            # Load geospatial data
            rio_path = file_path.replace("hdr", "img")
            with rio.open(rio_path) as dataset:
                self.transform = dataset.transform

            # Display the data using the updated method
            self.display_data()

    def display_data(self):
        if self.data is not None:
            # Determine the stretch limits for each band
            self.left_red_min_stretch_var = tk.DoubleVar(
                value=np.percentile(self.data.read_band(self.default_rgb_bands[0]), 2))
            self.left_red_max_stretch_var = tk.DoubleVar(
                value=np.percentile(self.data.read_band(self.default_rgb_bands[0]), 98))
            self.left_green_min_stretch_var = tk.DoubleVar(
                value=np.percentile(self.data.read_band(self.default_rgb_bands[1]), 2))
            self.left_green_max_stretch_var = tk.DoubleVar(
                value=np.percentile(self.data.read_band(self.default_rgb_bands[1]), 98))
            self.left_blue_min_stretch_var = tk.DoubleVar(
                value=np.percentile(self.data.read_band(self.default_rgb_bands[2]), 2))
            self.left_blue_max_stretch_var = tk.DoubleVar(
                value=np.percentile(self.data.read_band(self.default_rgb_bands[2]), 98))

            # Use the stretch limits to display the image
            self.display_left_data(self.default_rgb_bands)

    def stretch_band(self, band, stretch_limits, gamma=1.0, apply_clahe=False):
        min_stretch, max_stretch = stretch_limits
        # Clip and normalize the band
        stretched_band = np.clip(band, min_stretch, max_stretch)
        stretched_band = (stretched_band - min_stretch) / (max_stretch - min_stretch)

        # Apply gamma correction
        if gamma != 1.0:
            stretched_band = np.power(stretched_band, gamma)

        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        if apply_clahe:
            stretched_band = exposure.equalize_adapthist(stretched_band, clip_limit=0.03)

        return stretched_band

    def display_left_data(self, band_indices):
        # Stretch limits for each channel
        left_red_stretch = (self.left_red_min_stretch_var.get(), self.left_red_max_stretch_var.get())
        left_green_stretch = (self.left_green_min_stretch_var.get(), self.left_green_max_stretch_var.get())
        left_blue_stretch = (self.left_blue_min_stretch_var.get(), self.left_blue_max_stretch_var.get())

        # Extract the RGB bands
        left_rgb_image = self.data[:, :, [band_indices[0], band_indices[1], band_indices[2]]]

        # Apply stretching, gamma correction, and CLAHE to each band
        gamma_value = 0.8  # Adjust gamma to lighten dark areas, <1 for lightening, >1 for darkening
        left_rgb_image[:, :, 0] = self.stretch_band(left_rgb_image[:, :, 0], left_red_stretch, gamma=gamma_value,
                                                    apply_clahe=True)
        left_rgb_image[:, :, 1] = self.stretch_band(left_rgb_image[:, :, 1], left_green_stretch, gamma=gamma_value,
                                                    apply_clahe=True)
        left_rgb_image[:, :, 2] = self.stretch_band(left_rgb_image[:, :, 2], left_blue_stretch, gamma=gamma_value,
                                                    apply_clahe=True)

        # Display the image using matplotlib
        plt.imshow(left_rgb_image)
        plt.title('Enhanced RGB Composite of Spectral Data')
        plt.axis('off')
        plt.show()

        # Update window title with file name
        name = self.data.filename.split('/')[-1].split('.')[0]
        self.root.title(f"Spectral Cube Analysis Tool: {name}")


if __name__ == "__main__":
    root = tk.Tk()
    app = SpectralDataViewer(root)
    root.mainloop()
