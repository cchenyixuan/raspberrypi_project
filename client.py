import socket
import threading
import time
import traceback

import numpy as np
import cv2
from zlib import compress, decompress


class Client:
    def __init__(self, host="172.25.25.30", data_port=8004, status_port=8005):
        self.server_type = "UDP"
        self.width = 800
        self.height = 600
        # host and port config
        self.host = host
        self.data_port = data_port
        self.status_port = status_port
        # status pipe line
        self.status_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.status_socket.connect((self.host, self.status_port))
        print("Status connection established!")

        time.sleep(1)
        # data pipe line
        if self.server_type == "TCP":
            self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.data_socket.connect((self.host, self.data_port))
            self.data_socket.sendall(bytes(f'Hello Server {str(self.width).zfill(4)} {str(self.height).zfill(4)}', encoding='utf-8'))
        elif self.server_type == "UDP":
            self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.data_socket.sendto(bytes(f'Hello Server {str(self.width).zfill(4)} {str(self.height).zfill(4)}', encoding='utf-8'), (host, data_port))
            message, server = self.data_socket.recvfrom(1024)
            print(message, server)
            if message == b"Hello Client":
                print("Data connection established! ")
        time.sleep(1)
        self.platform_degrees = [0.0, 0.0]
        self.platform_degrees_delta = [0.0, 0.0]
        # data received and cache
        self.buffer = []
        self.cache = b""
        self.tmp = []
        # console message
        print("Initialized.")

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
                data = b""
                if self.server_type == "TCP":
                    data = self.data_socket.recv(1024)
                    # if data is received
                    if data[-4:] == b'done':
                        # one frame is received
                        self.tmp.append(data[:-4])
                        self.buffer.append(b''.join(self.tmp))
                        # print("received one frame by <receive data>", len(self.buffer))
                        self.tmp = []
                        # self.status_setter((self.server_ready, True))
                    else:
                        # continue receiving
                        self.tmp.append(data)
                elif self.server_type == "UDP":
                    data, server = self.data_socket.recvfrom(1024)
                    print(len(data), str(data[-9:-6], encoding="utf-8"), str(data[-6:-3], encoding="utf-8"), str(data[-3:], encoding="utf-8"), data[-9:], server)
                    # if data is received
                    if data[-6:-3] == data[-3:]:

                        # one frame is received
                        self.tmp.append(data)
                        packs = [pack for pack in self.tmp if pack[-9:-6] == data[-9:-6]]
                        sorted_packs = [b'' for _ in range(int(data[-6:-3])+1)]
                        if len(packs) != len(sorted_packs):
                            print("incomplete!")
                        else:
                            for pack in packs:
                                index = int(pack[-3:])
                                sorted_packs[index] = pack[:-9]
                            self.buffer.append(b''.join(sorted_packs))
                            # self.buffer.append(b''.join((pack[:-6] for pack in self.tmp if pack[-6:-4] == data[-6:-4])))
                            # print("received one frame by <receive data>", len(self.buffer))
                            self.tmp = []
                        # self.status_setter((self.server_ready, True))
                    else:
                        # continue receiving
                        self.tmp.append(data)
            except ConnectionAbortedError:
                print("Data-receiver offline: Server connection lostCA")
                break
            except ConnectionResetError:
                print("Data-receiver offline: Server connection resetC")
                break
            except TimeoutError:
                print("Data-receiver timeout! ")
                self.tmp = []
                # self.status_setter((self.server_ready, True))
            except OSError as e:
                print(data)
                print(e)
                print("Data-receiver offline: Server connection resetO")
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
            try:
                cv2.imshow('Camera0', cv2.imdecode(np.frombuffer(frame_buffer, dtype=np.uint8), 1))
            except:
                traceback.print_exc()

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
        end = time.time()
        print(end-start, total/(end-start))

    def stop(self):
        # Destroy all the windows
        cv2.destroyAllWindows()
        # disconnect to server
        self.status_socket.sendall(b"end end")
        self.status_socket = self.status_socket.close()  # None
        self.data_socket = self.data_socket.close()  # None

    @staticmethod
    def zip_frame(buffer):
        return compress(buffer)

    @staticmethod
    def unzip_frame(buffer):
        return decompress(buffer)

    def __call__(self, *args, **kwargs):
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
