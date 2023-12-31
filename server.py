import socket
import sys
import threading
import time
import traceback

import numpy as np
import cv2
from zlib import compress, decompress

from cloud_platform import CloudPlatform


class CameraServer:
    def __init__(self, fps=60, width=400, height=400, host="172.25.25.30", data_port=8004, status_port=8005):
        self.buffer = []

        self.server_type = "UDP"
        # camera angles X and Y axis
        self.camera_angles = [0.0, 0.0]
        self.platform = CloudPlatform()
        self.platform(self.camera_angles)
        time.sleep(1)
        print("Platform Ready.")

        self.status_changed = False

        self.fps = fps
        self.width = width
        self.height = height
        # init camera
        self.camera = None
        self.test_camera()
        # server
        # host and port config
        self.host = host
        self.data_port = data_port
        self.status_port = status_port
        # status server
        self.status_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.status_server.bind((self.host, self.status_port))
        self.status_server.listen()
        self.status_socket = None
        # data server
        if self.server_type == "TCP":
            self.data_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.data_server.bind((self.host, self.data_port))
            self.data_server.listen()
            self.data_socket = None
        elif self.server_type == "UDP":
            self.data_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.data_server.bind((self.host, self.data_port))
            self.data_socket = None
            self.address = None
            # measurement
        self.data_socket_bytes_flux = 0
        self.status_socket_bytes_flux = 0
        # controllers
        self.server_should_close = False
        self.count = 0

    def init_camera(self):
        if sys.platform == 'linux':
            self.camera = cv2.VideoCapture(0, cv2.CAP_V4L2)  # direct show  CAP_DSHOW
        else:
            self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # direct show  CAP_DSHOW
        if self.camera.isOpened():
            print("Camera is Online.")
        else:
            print("Camera Error!")

        self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('M', 'J', 'P', 'G'))
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)  # width
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)  # height
        self.camera.set(cv2.CAP_PROP_FPS, self.fps)  # FPS
        print(f"Camera FPS: {self.camera.get(cv2.CAP_PROP_FPS)} Width: {self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)} Height: {self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)}.")

    def close_camera(self):
        if self.camera:
            self.camera.release()
            print("Camera is Offline")
            self.camera = None
        else:
            pass

    def reset(self, trigger=None):
        print(f"Reset all connections. <Trigger: {trigger}>")
        self.status_socket = None
        if self.server_type == "TCP":
            self.data_socket = None
        elif self.server_type == "UDP":
            # self.data_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # self.data_server.bind((self.host, self.data_port))
            self.data_socket = None
        self.camera_angles = [0.0, 0.0]
        self.platform(self.camera_angles)
        self.close_camera()
        self.buffer = []
        print(self.count)
        self.count = 0

    def test_camera(self):
        if sys.platform == 'linux':
            self.camera = cv2.VideoCapture(0, cv2.CAP_V4L2)  # direct show  CAP_DSHOW
        else:
            self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # direct show  CAP_DSHOW
        if self.camera.isOpened():
            print("Camera Test Pass")
            self.camera.release()
            self.camera = None
        else:
            print("Camera Test Failed")
            self.camera.release()
            self.camera = None
            raise Exception("Camera Unable to Initialize.")

    def send_status(self):
        # send "ServerReady" if server is ready
        while self.status_socket:
            try:
                if self.status_changed:
                    # camera angle is changed by client
                    self.status_socket_bytes_flux += 13
                    message = bytes(
                        f'{str(round(self.camera_angles[0], 2)).zfill(6)} {str(round(self.camera_angles[1], 2)).zfill(6)}',
                        encoding='utf-8'
                    )

                    self.status_socket.settimeout(5)
                    self.status_socket.sendall(message)
                    self.status_changed = False
            except ConnectionAbortedError:
                print("Client status connection lost")
                print("Stop sending status")
                self.status_socket = None
                break
            except ConnectionResetError:
                print("Client status connection lost")
                print("Stop sending status")
                self.status_socket = None
                break
            except AttributeError:
                self.status_socket = None
                break
            except BrokenPipeError:
                self.status_socket = None
                break
            time.sleep(0.1)

    def receive_status(self):
        # mark client as ready when receive "ClientReady"
        while self.status_socket:
            try:
                message = self.status_socket.recv(1024*16)
                # print("Message ", message)
                new_camera_angles = [float(degree) for degree in str(message, encoding='utf-8')[-13:].split(" ")]
                if new_camera_angles[0] != self.camera_angles[0] or new_camera_angles[1] != self.camera_angles[1]:
                    self.camera_angles = new_camera_angles
                    self.status_changed = True
                    self.platform(self.camera_angles)
                    print(f"New camera-angle is set to {self.camera_angles[0]} {self.camera_angles[1]}.")

            except ConnectionAbortedError:
                print("Client status connection lost")
                print("Stop receiving status")
                self.status_socket = None
                break
            except ConnectionResetError:
                print("Client status connection lost")
                print("Stop receiving status")
                self.status_socket = None
                break
            except AttributeError:
                self.status_socket = None
                break
            except BrokenPipeError:
                self.status_socket = None
                break
            except ValueError:
                self.status_socket = None
                print("ValueError at receive status")
                break
            time.sleep(0.01)

    def establish_status_connection(self) -> None:
        """
        start status-server service forever
        :return: None
        """
        while not self.server_should_close:
            self.status_socket, addr = self.status_server.accept()
            # following codes will not be run until a client connects this server
            print(f"Status server connected by {addr}")
            send_status = threading.Thread(target=self.send_status)
            send_status.daemon = True
            receive_status = threading.Thread(target=self.receive_status)
            receive_status.daemon = True
            send_status.start()
            receive_status.start()
            # status service is opened
            while self.status_socket:
                # status-socket is alive, do nothing
                time.sleep(1)
            # status service is closed
            self.reset(trigger="establish_status_connection")

    def establish_data_connection(self) -> None:
        """
        start data-server service forever
        :return: None
        """
        while not self.server_should_close:
            if self.server_type == "TCP":
                self.data_socket, addr = self.data_server.accept()
                # following codes will not be run until a client connects this server
                print(f"Message <establish_data_connection>: Data server connected by {addr}")
                # receive greetings and settings
                message = self.data_socket.recv(1024)
                self.width, self.height = [int(item) for item in str(message[-9:], encoding="utf-8").split(' ')]
                print(f"Width, Height set to {self.width} {self.height}")
            elif self.server_type == "UDP":
                message, self.address = self.data_server.recvfrom(1024)
                print("Message <establish_data_connection>: ", message, self.address)
                self.width, self.height = [int(item) for item in str(message[-9:], encoding="utf-8").split(' ')]
                print(f"Width, Height set to {self.width} {self.height}")
                self.data_socket = self.data_server
                self.data_socket.sendto(b"Hello Client", self.address)
            # data-socket is ready, start sending data
            send_data = threading.Thread(target=self.send_data)
            send_data.daemon = True
            send_data.start()
            # data service is opened
            while self.data_socket:
                # data-socket is alive, do nothing
                time.sleep(1)
            # data service is closed
            self.reset(trigger="establish_data_connection")

    def send_data(self):
        while self.data_socket:
            try:
                if self.buffer:
                    frame = self.zip_frame(cv2.imencode(".jpg", self.buffer.pop(0))[1])
                    self.data_socket_bytes_flux += len(frame)
                    self.count += 1
                    # TCP
                    if self.server_type == "TCP":
                        self.data_socket.sendall(frame)
                        self.data_socket.sendall(b'done')
                    # UDP
                    if self.server_type == "UDP":
                        for pack in self.slice_data_udp(frame, 1024):
                            #print(len(pack))
                            #if len(pack) > 4096:
                            #    print(pack)
                            #    self.data_socket = None
                            self.data_socket.sendto(pack, self.address)
                else:
                    ...
            except ConnectionAbortedError:
                print("Client data connection lost")
                print("Stop sending data")
                self.data_socket = None
                break
            except ConnectionResetError:
                print("Client data connection lost")
                print("Stop sending data")
                self.data_socket = None
                break
            except BrokenPipeError:
                self.data_socket = None
                break
            except AttributeError:
                self.data_socket = None
                break
            except Exception:
                with open(r"log.txt", "a") as f:
                    f.write(f"{time.ctime(time.time())}\n")
                    traceback.print_exc(file=f)
                    f.close()
                print("Error saved to log.txt.")
                self.data_socket = None
                break

    @staticmethod
    def slice_data_udp(data: bytes, pack_size=4096):
        """
        divide data to packs
        :param data: bytes
        :param pack_size: slice-size
        :return: packs sliced
        """
        data_pack_size = pack_size - 9
        pack_length = len(data) // data_pack_size + bool(len(data) % data_pack_size)
        salt = np.random.randint(0, 999)
        packs = (data[step * data_pack_size: (step + 1) * data_pack_size] + bytes(
            f'{salt}'.zfill(3) + f'{pack_length - 1}'.zfill(3) + f'{step}'.zfill(3), encoding='utf-8') for step in
                 range(pack_length))
        return packs

    @staticmethod
    def zip_frame(buffer):
        return compress(buffer)

    @staticmethod
    def unzip_frame(buffer):
        return decompress(buffer)

    def establish_stream_service(self) -> None:
        """
        start stream service forever
        :return: None
        """
        while not self.server_should_close:
            # start stream service if connection is established else wait
            if self.status_socket and self.data_socket:
                stream = threading.Thread(target=self.stream)
                stream.daemon = True
                stream.start()
                # stream is opened
                while self.status_socket and self.data_socket:
                    # connection is alive, do nothing
                    time.sleep(1)
                # stream is stopped
                self.reset(trigger="establish_stream_service")
            else:
                # wait
                time.sleep(1)

    def stream(self):
        # initialize camera device if data-link has been established
        while self.status_socket and self.data_socket:
            # check if camera is armed
            if not self.camera:
                # camera is not armed, try arming
                self.init_camera()
                time.sleep(1)
            else:
                # camera is ready, capture buffer
                try:
                    assert self.camera.isOpened() is True
                    self.buffer.append(self.camera.read()[1])
                    # discard redundant buffer
                    if len(self.buffer) >= 2:
                        self.buffer = self.buffer[-2:]
                except AssertionError:
                    print("Camera Error! Restarting...", file=sys.stderr)
                    self.close_camera()
                    time.sleep(1)
                    self.init_camera()
                    time.sleep(1)

        # connection is closed, close camera
        if self.camera:
            self.close_camera()
            self.data_socket = None

    def capture(self):
        ret, frame = self.camera.read()
        return frame

    def set_resolution(self, width: int, height: int):
        self.width = width
        self.height = height
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)  # width
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)  # height
        print(f"Resolution is set to {self.width}x{self.height}.")

    def set_fps(self, fps: int):
        self.fps = fps
        self.camera.set(cv2.CAP_PROP_FPS, self.fps)  # FPS
        print(f"FPS is set to {self.fps}.")

    def stop(self):
        time.sleep(1)
        self.camera.release()
        self.camera = None
        # Destroy all the windows
        cv2.destroyAllWindows()

    def preview(self):
        while not self.server_should_close:
            preview = True
            s = time.time()
            count = 0
            while preview:
                if self.buffer and self.camera:
                    cv2.imshow('Camera0', self.buffer[-1])
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("Camera stopped by keyboard control.")
                    break
                if self.status_socket and self.data_socket:
                    preview = True
                else:
                    preview = False
                    cv2.destroyAllWindows()
                    time.sleep(1)

    def measure_network_flux(self):
        while not self.server_should_close:
            # start measurement if connection is established else wait
            if self.status_socket and self.data_socket:
                start = time.time()
                self.data_socket_bytes_flux = 0
                self.status_socket_bytes_flux = 0
                while time.time() - start < 1.0:
                    time.sleep(0.01)
                print(
                    f"NetworkFlux: {round((self.data_socket_bytes_flux + self.status_socket_bytes_flux) / (time.time() - start) / 1024, 3)} kb/s DataFlux: {round(self.data_socket_bytes_flux / (time.time() - start) / 1024, 3)} kb/s  StatusFlux: {round(self.status_socket_bytes_flux / (time.time() - start) / 1024, 3)} kb/s RemainingBuffer: {len(self.buffer)}"
                )
                time.sleep(1.0)
            else:
                # wait
                time.sleep(1)

    def __call__(self, *args, **kwargs):
        # Todo: status and data server should be opened or closed at same time to avoid error!!
        # open 2 ports, wait connection, keep connection, send data
        establish_status_connection = threading.Thread(target=self.establish_status_connection)
        establish_status_connection.daemon = True
        establish_status_connection.start()
        establish_data_connection = threading.Thread(target=self.establish_data_connection)
        establish_data_connection.daemon = True
        establish_data_connection.start()
        # stream service
        establish_stream_service = threading.Thread(target=self.establish_stream_service)
        establish_stream_service.daemon = True
        establish_stream_service.start()
        # server is ready
        # self.server_ready = True
        # net-flux measurer
        measurer = threading.Thread(target=self.measure_network_flux)
        measurer.daemon = True
        measurer.start()
        # preview thread
        # preview = threading.Thread(target=self.preview)
        # preview.daemon = True
        # preview.start()
        # server loop
        while not self.server_should_close:
            time.sleep(1)


class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen()
        self.socket = None


if __name__ == "__main__":
    camera_server = CameraServer()
    camera_server()
