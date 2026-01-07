# Example of converting a .png file to .ico format using the Pillow library
from PIL import Image
image = Image.open("./icon.png")
image.save("./icon.ico", format="ICO")