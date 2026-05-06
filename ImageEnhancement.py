import PIL.Image

class ImageEnhancement:
    def __init__(self):
        pass

    def standardize_image(self, image_path):
        """
            Resize and recolor image to geoclip's input expectations
        """
        image = PIL.Image.open(image_path).convert("RGB")
        image = image.resize((224, 224))
        image.save(image_path)

        return
    
    def get_grid_patches(self, image, grid=2):
        """
            Convert Image into grid^2 subsections. i.e. size=2 means make two cuts (horizontal + vertical), 
            then return the 4 new images. 

            Ideally we don't want images that reveal nothing to be included in geoclips guess. For example,
            if a majority of the image is a plain white mug with nothing notable about it, we should really be
            focusing on the background of the image.
        """

        w, h = image.size

        patches = []

        for i in range(grid):
            for j in range(grid):
                left = j * w // grid
                top = i * h // grid
                right = (j + 1) * w // grid
                bottom = (i + 1) * h // grid

                patch = image.crop((left, top, right, bottom))
                patches.append(patch)

        return patches
