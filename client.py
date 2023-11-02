import socket
import threading
import time
import re
import numpy as np
import cv2
from zlib import compress, decompress
import zlib


class Client:
    def __init__(self, host="172.25.25.25", data_port=8000, status_port=8080):
        # host and port config
        self.host = host
        self.data_port = data_port
        self.status_port = status_port
        # status pipe line
        self.status_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.status_socket.connect((self.host, self.status_port))
        time.sleep(1)
        # data pipe line
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.connect((self.host, self.data_port))

        # server client status
        self.server_ready = False
        self.client_ready = False
        self.status_to_byte = {(False, False): b"00", (True, False): b"10", (False, True): b"01", (True, True): b"11"}
        self.byte_to_status = {b"00": (False, False), b"10": (True, False), b"01": (False, True), b"11": (True, True)}
        self.status_changed = True
        # data received and cache
        self.buffer = []
        self.cache = b""
        self.tmp = []
        # console message
        print("Connection established.")

    def status_setter(self, flag: tuple[bool, bool]):
        """
        Judge if status changed and set all status
        :param flag: tuple[server_ready, client_ready]
        :return: None
        """
        if (self.server_ready, self.client_ready) != flag:
            self.server_ready, self.client_ready = flag
            self.status_changed = True
        else:
            pass

    def send_status(self):
        while self.status_socket:
            try:
                self.status_socket.sendall(self.status_to_byte[(self.server_ready, self.client_ready)])
            except ConnectionAbortedError:
                print("Status-sender offline: Server connection lost")
                break
            except ConnectionResetError:
                print("Status-sender offline: Server connection reset")
                break
            time.sleep(1.0)

    def receive_status(self):
        # mark server as ready when receive "ServerReady"
        while self.status_socket:
            try:
                message = self.status_socket.recv(1024)
                print("Message ", message)
                if len(message) >= 2:
                    self.status_setter(self.byte_to_status[message[-2:]])
                print("Server: ", self.server_ready)
            except ConnectionAbortedError:
                print("Status-receiver offline: Server connection lost")
                break
            except ConnectionResetError:
                print("Status-receiver offline: Server connection reset")
                break
            time.sleep(1.0)

    def receive_data(self):
        # receive video from server
        while self.data_socket:
            # receive data
            try:
                # receive data from data socket
                # self.data_socket.settimeout(1)
                data = self.data_socket.recv(1024)
                # if data is received
                if data[-4:] == b"done":
                    # one frame is received
                    self.tmp.append(data[:-4])
                    self.buffer.append(b''.join(self.tmp))
                    print("received one frame by <receive data>", len(self.buffer))
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
        # endless render
        while True:

            # discard older data
            if len(self.buffer) >= 60:
                self.buffer = self.buffer[-60:]
            # update frame if buffer is not empty
            if len(self.buffer) >= 1:
                frame = self.buffer.pop(0)
                try:
                    frame_buffer = self.unzip_frame(frame)
                except:  # zlib.error: Error -3 while decompressing data: incorrect header check
                    print("Incomplete frame_buffer! Data has been discarded!")
            else:
                # frame will not be updated
                pass
            cv2.imshow('Camera0', cv2.imdecode(np.frombuffer(frame_buffer, dtype=np.uint8), 1))
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Camera stopped by keyboard control.")
                # if self.status_socket:
                #     self.status_socket.close()
                # if self.data_socket:
                #     self.data_socket.close()
                break
        self.stop()

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