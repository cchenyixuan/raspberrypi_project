import time
import re
import numpy as np
import cv2

fourcc_names = ['CAP_PROP_POS_MSEC', 'CAP_PROP_POS_FRAMES', 'CAP_PROP_POS_AVI_RATIO', 'CAP_PROP_FRAME_WIDTH', 'CAP_PROP_FRAME_HEIGHT', 'CAP_PROP_FPS', 'CAP_PROP_FOURCC', 'CAP_PROP_FRAME_COUNT', 'CAP_PROP_FORMAT', 'CAP_PROP_MODE', 'CAP_PROP_BRIGHTNESS', 'CAP_PROP_CONTRAST', 'CAP_PROP_SATURATION', 'CAP_PROP_HUE', 'CAP_PROP_GAIN', 'CAP_PROP_EXPOSURE', 'CAP_PROP_CONVERT_RGB', 'CAP_PROP_WHITE_BALANCE_BLUE_U', 'CAP_PROP_RECTIFICATION', 'CAP_PROP_MONOCHROME', 'CAP_PROP_SHARPNESS', 'CAP_PROP_AUTO_EXPOSURE', 'CAP_PROP_GAMMA', 'CAP_PROP_TEMPERATURE', 'CAP_PROP_TRIGGER', 'CAP_PROP_TRIGGER_DELAY', 'CAP_PROP_WHITE_BALANCE_RED_V', 'CAP_PROP_ZOOM', 'CAP_PROP_FOCUS', 'CAP_PROP_GUID', 'CAP_PROP_ISO_SPEED', 'CAP_PROP_BACKLIGHT', 'CAP_PROP_PAN', 'CAP_PROP_TILT', 'CAP_PROP_ROLL', 'CAP_PROP_IRIS', 'CAP_PROP_SETTINGS', 'CAP_PROP_BUFFERSIZE', 'CAP_PROP_AUTOFOCUS']

if __name__ == "__main__":
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y', 'U', 'Y', '2'))
    camera.set(cv2.CAP_PROP_FPS, 30)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 720)  # width
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)

    print(camera.isOpened())
    data = []
    start = time.time()
    for _ in range(100):

        data.append(camera.read()[1])
        print(len(data)/(time.time()-start+0.00001))


