import requests
import os
import io
from PIL import Image

c_ImageAddress = "https://opengraph.githubassets.com/50829375aae1df9ce9fec1881829ab50997306cef04129bd38e65b2267576d63/rafa-br34/PlaceIPv6Bot"
c_OutputName = "image.png"
c_RunTime = "10m"
c_RootPath = ""

def main():
	ImageData = requests.get(c_ImageAddress)
	if not ImageData:
		print("Failed To Acquire Canvas Image(Exception).")
		return exit(1)
	elif ImageData.status_code != 200:
		print(f"Failed To Acquire Image. Status Code {ImageData.status_code}")
		return exit(1)
	
	TargetImage = Image.open(io.BytesIO(ImageData.content))
	NewSize = max(*TargetImage.size)
	NewImage = Image.new("RGB", [NewSize, NewSize], color=0xFFFFFF)
	NewImage.paste(TargetImage, [0, int((NewSize / 2) - (TargetImage.size[1] / 2))])
	NewImage.save(f"{c_RootPath}{c_OutputName}")
	os.system(f"sudo timeout -k {c_RunTime} {c_RunTime} python {c_RootPath}PlaceIPv6.py")



if __name__ == '__main__':
	main()