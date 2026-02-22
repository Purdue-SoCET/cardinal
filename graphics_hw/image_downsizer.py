#helper script to downscale image to test filtering


from PIL import Image

image = Image.open("sooraj.jpg")
original_width, original_height = image.size

new_width = int(original_width/8)
new_height = int(original_height/8)


resized_image = image.resize((new_width, new_height), Image.LANCZOS)
resized_image.save("sooraj2.jpg")