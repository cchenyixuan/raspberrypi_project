import email.message
import socket
import threading
import time
import re
import numpy as np
import cv2
from zlib import compress, decompress
import zlib


class Client:
    def __init__(self, host="192.168.0.103", data_port=8777, status_port=8778):
        self.server_type = "UDP"
        self.width = 720
        self.height = 640
        # host and port config
        self.host = host
        self.data_port = data_port
        self.status_port = status_port
        # status pipe line
        self.status_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.status_socket.connect((self.host, self.status_port))
        time.sleep(1)
        # data pipe line
        if self.server_type == "TCP":
            self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.data_socket.connect((self.host, self.data_port))
        elif self.server_type == "UDP":
            self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.data_socket.sendto(bytes(f'Hello Server {str(self.width).zfill(4)} {str(self.height).zfill(4)}', encoding='utf-8'), (host, data_port))

        # server client status
        self.server_ready = False
        self.client_ready = False

        self.platform_degrees = [0.0, 0.0]
        self.platform_degrees_delta = [0.0, 0.0]
        # data received and cache
        self.buffer = []
        self.cache = b""
        self.tmp = []
        # console message
        print("Connection established.")

    def send_status(self):
        while self.status_socket:
            try:
                self.status_socket.sendall(bytes(f'{str(round(self.platform_degrees[0], 2)).zfill(6)} {str(round(self.platform_degrees[1], 2)).zfill(6)}', encoding='utf-8'))
            except ConnectionAbortedError:
                print("Status-sender offline: Server connection lost")
                break
            except ConnectionResetError:
                print("Status-sender offline: Server connection reset")
                break
            time.sleep(0.01)

    def receive_status(self):
        # mark server as ready when receive "ServerReady"
        while self.status_socket:
            try:
                message = self.status_socket.recv(1024)
                print("Message ", message)
                print(f'Server camera-angles {[float(degree) for degree in str(message, encoding="utf-8")[-13:].split(" ")]}.')
            except ConnectionAbortedError:
                print("Status-receiver offline: Server connection lost")
                break
            except ConnectionResetError:
                print("Status-receiver offline: Server connection reset")
                break
            time.sleep(0.1)

    def receive_data(self):
        # receive video from server
        while self.data_socket:
            # receive data
            try:
                # receive data from data socket
                # self.data_socket.settimeout(1)
                if self.server_type == "TCP":
                    data = self.data_socket.recv(1024)
                elif self.server_type == "UDP":
                    data, server = self.data_socket.recvfrom(4096*10)
                    # print(len(data), data[-10:], server)
                # if data is received
                if data[-4:-2] == data[-2:]:
                    # one frame is received
                    self.tmp.append(data)
                    self.buffer.append(b''.join((pack[:-6] for pack in self.tmp if pack[-6:-4] == data[-6:-4])))
                    # print("received one frame by <receive data>", len(self.buffer))
                    self.tmp = []
                    # self.status_setter((self.server_ready, True))
                else:
                    # continue receiving
                    self.tmp.append(data)
            except ConnectionAbortedError:
                print("Data-receiver offline: Server connection lost")
                break
            except ConnectionResetError:
                print("Data-receiver offline: Server connection reset")
                break
            except TimeoutError:
                print("Data-receiver timeout! ")
                self.tmp = []
                # self.status_setter((self.server_ready, True))
            except OSError:
                print("Data-receiver offline: Server connection reset")
                break

    def render_stream(self):
        # check if stream comes in
        while True:
            if len(self.buffer) >= 1:
                frame = self.buffer.pop(0)
                print("Stream Incoming...")
                try:
                    frame_buffer = self.unzip_frame(frame)
                    print("Stream Verified!")
                    break
                except:  # zlib.error: Error -3 while decompressing data: incorrect header check
                    print("Stream data not complete, retrying...")
            else:
                time.sleep(0.01)
        # set window callback
        cv2.namedWindow("Camera0")

        def mouse_clb(*event):
            if event[0] == 1:
                self.platform_degrees_delta = [-(event[1] - self.width/2) / (self.width/2) * 90, min(40, (event[2] - self.height/2) / (self.height/2) * 90)]
            if event[3] == 1:
                delta = [-(event[1] - self.width/2) / (self.width/2) * 90, min(40, (event[2] - self.height/2) / (self.height/2) * 90)]
                self.platform_degrees = [
                    min(max(self.platform_degrees[0] + delta[0] - self.platform_degrees_delta[0], -90), 90),
                    min(max(self.platform_degrees[1] + delta[1] - self.platform_degrees_delta[1], -90), 40)]
                self.platform_degrees_delta = delta

        cv2.setMouseCallback("Camera0", mouse_clb)
        # endless render
        correct = 0
        total = 0
        start = time.time()
        while True:
            # discard older data
            if len(self.buffer) >= 60:
                self.buffer = self.buffer[-60:]
            # update frame if buffer is not empty
            if len(self.buffer) >= 1:
                frame = self.buffer.pop(0)
                try:
                    frame_buffer = self.unzip_frame(frame)
                    correct += 1
                    total += 1
                except:  # zlib.error: Error -3 while decompressing data: incorrect header check
                    print("Incomplete frame_buffer! Data has been discarded!")
                    total += 1
            else:
                # frame will not be updated
                pass
            cv2.imshow('Camera0', cv2.imdecode(np.frombuffer(frame_buffer, dtype=np.uint8), 1))


            if total % 600 == 0 and total != 0:
                print(f"Accuracy: {correct / total}, correct: {correct}, total: {total}")
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Camera stopped by keyboard control.")
                # if self.status_socket:
                #     self.status_socket.close()
                # if self.data_socket:
                #     self.data_socket.close()
                print(f"Accuracy: {correct / total}, correct: {correct}, total: {total}")
                break
        self.stop()
        print(time.time()-start, total/(time.time()-start))

    def stop(self):
        # Destroy all the windows
        cv2.destroyAllWindows()
        # disconnect to server
        self.status_socket = self.status_socket.close()  # None
        self.data_socket = self.data_socket.close()  # None

    @staticmethod
    def zip_frame(buffer):
        return compress(buffer)

    @staticmethod
    def unzip_frame(buffer):
        return decompress(buffer)

    def __call__(self, *args, **kwargs):
        self.client_ready = True
        send_status = threading.Thread(target=self.send_status)
        send_status.start()
        receive_status = threading.Thread(target=self.receive_status)
        receive_status.start()
        receive_data = threading.Thread(target=self.receive_data)
        receive_data.start()
        # process_stream = threading.Thread(target=self.process_stream)
        # process_stream.start()
        self.render_stream()


if __name__ == "__main__":
    camera_client = Client()
    camera_client()