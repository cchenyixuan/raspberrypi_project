import socket
import threading
import time
import re
import numpy as np
import cv2
from zlib import compress, decompress


def server(data_source, host="172.25.25.26", port=8888):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, port))
    s.listen()
    server_should_terminate = False
    while not server_should_terminate:
        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")
            while True:
                try:
                    data = conn.recv(1024)
                    if data == b"terminate":
                        server_should_terminate = True
                        break
                    conn.sendall(bytes(f"X: {data_source.servo_value[0]}, Y: {data_source.servo_value[1]}, Z: 0.0, W: 0.0,", "utf-8"))
                    # print(f"request: {data}")
                except ConnectionAbortedError:
                    print("Client disconnected")
                    s.listen()
                    break
                except ConnectionResetError:
                    s.listen()
                    break


class CameraServer:
    def __init__(self, fps=30, width=1080, height=720, host="172.25.25.25", data_port=8000, status_port=8080):
        self.buffer = []

        self.client_ready = False  # client is ready to receive data(client-tmp-buffer is empty)
        self.server_ready = False  # buffer is not empty
        self.status_to_byte = {(False, False): b"00", (True, False): b"10", (False, True): b"01", (True, True): b"11"}
        self.byte_to_status = {b"00": (False, False), b"10": (True, False), b"01": (False, True), b"11": (True, True)}
        self.status_changed = True
        # status, data, stream service states
        self.server_status = [False, False, False]
        self.should_print_underline = False

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
        self.data_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_server.bind((self.host, self.data_port))
        self.data_server.listen()
        self.data_socket = None
        # measurement
        self.data_socket_bytes_flux = 0
        self.status_socket_bytes_flux = 0
        # controllers
        self.server_should_close = False

    def init_camera(self):
        self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # direct show  CAP_DSHOW
        if self.camera.isOpened():
            print("Camera is Online.")
        else:
            print("Camera Error!")
        self.camera.set(cv2.CAP_PROP_FPS, self.fps)  # FPS
        self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('m', 'j', 'p', 'g'))
        self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('M', 'J', 'P', 'G'))
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)  # width
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)  # height

    def close_camera(self):
        self.camera.release()
        print("Camera is Offline")
        self.camera = None

    def test_camera(self):
        self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # direct show  CAP_DSHOW  CAP_V4L2
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
                self.status_socket_bytes_flux += 2
                self.status_socket.sendall(self.status_to_byte[(self.server_ready, self.client_ready)])
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
            time.sleep(1.0)

    def receive_status(self):
        # mark client as ready when receive "ClientReady"
        while self.status_socket:
            try:
                message = self.status_socket.recv(1024)
                print("Message ", message)
                if len(message) >= 2:
                    client_new_flag = self.byte_to_status[message[-2:]][1]
                    if self.client_ready != client_new_flag:
                        self.status_changed = True
                        self.client_ready = client_new_flag
                print("Client: ", self.client_ready)

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
            time.sleep(1.0)

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
            self.server_status[0] = True
            while self.status_socket:
                # status-socket is alive, do nothing
                time.sleep(1)
            # status service is closed
            self.server_status[0] = False

    def establish_data_connection(self) -> None:
        """
        start data-server service forever
        :return: None
        """
        while not self.server_should_close:
            self.data_socket, addr = self.data_server.accept()
            # following codes will not be run until a client connects this server
            print(f"Data server connected by {addr}")
            send_data = threading.Thread(target=self.send_data)
            send_data.daemon = True
            send_data.start()
            # data service is opened
            self.server_status[1] = True
            while self.data_socket:
                # data-socket is alive, do nothing
                time.sleep(1)
            # data service is closed
            self.server_status[1] = False

    def send_data(self):
        while self.data_socket:
            try:
                if self.buffer:
                    # print(len(self.buffer), len(self.buffer[0]))
                    self.data_socket_bytes_flux += len(self.buffer[0])
                    self.data_socket.sendall(self.buffer.pop(0))
                    self.data_socket.sendall(b'done')
                    # print("send one frame.")
                    # self.server_ready = True
                else:
                    pass
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
            time.sleep(0.01)

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
                self.server_status[2] = True
                while self.status_socket and self.data_socket:
                    # connection is alive, do nothing
                    time.sleep(1)
                # stream is stopped
                self.server_status[2] = False
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
                buffer = self.zip_frame(cv2.imencode(".jpg", self.camera.read()[1])[1])
                self.buffer.append(buffer)
                # discard redundant buffer
                if len(self.buffer) >= 60:
                    self.buffer = self.buffer[-60:]
                # fps limit
                time.sleep(1 / self.fps)
        # connection is closed, close camera
        if self.camera:
            self.close_camera()

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
        self.camera.release()
        self.camera = None
        # Destroy all the windows
        cv2.destroyAllWindows()

    def preview(self):
        while not self.server_should_close:
            preview = True
            while preview:
                if self.buffer and self.camera:
                    cv2.imshow('Camera0', cv2.imdecode(np.frombuffer(self.unzip_frame(self.buffer[-1]), dtype=np.uint8), -1))
                    time.sleep(1/self.fps)
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
                    f"NetworkFlux: {round((self.data_socket_bytes_flux + self.status_socket_bytes_flux) / (time.time() - start) / 1024, 3)} kb/s DataFlux: {round(self.data_socket_bytes_flux / (time.time() - start) / 1024, 3)} kb/s  StatusFlux: {round(self.status_socket_bytes_flux / (time.time() - start) / 1024, 3)} kb/s RemainingBuffer: {len(self.buffer)}")
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
        preview = threading.Thread(target=self.preview)
        preview.daemon = True
        preview.start()
        # server loop
        self.server_ready = True
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
    ...




