import threading
import requests
import socket
import random
import select
import time
import math
import os
import io
from PIL import Image

from Networking import ICMPv6

c_WaitTime = 0.01 # Time to yield for each iteration
c_ChunkSize = 20 # The amount of pings to ping per iteration
c_RootAddress = "2a01:4f8:c012:f8e6" # Canvas base address
c_CanvasURL = "https://ssi.place/canvas.png" # Canvas base URL
c_TargetImage = "image.png" # Target image
c_MaxColorDifference = 4 # The maximum color difference(Used in every comparison). Recommended: 4, 8, 16
c_DrawMode = "CLOSEST" # In what order pixels will be drawn [CLOSEST, SCATTER, FIRST, LAST]
c_BufferSize = 32 # Socket buffer size, in MB


g_SharedData = {
    "Run": True,
    "WriteQueue": [],
    "CanvasSize": [512, 512],
}

def LinePrint(*args, sep=' '):
    ResultString = ""
    for Argument in args:
        ResultString += str(Argument) + sep
    
    PadLen = (os.get_terminal_size()[0] - len(ResultString)) - 1
    Padding = (PadLen > 0 and ('' * PadLen)) or ''
    print(ResultString, end=Padding + '\r')

def CompareColor(A, B):
    return math.sqrt((A[0] - B[0]) ** 2 + (A[1] - B[1]) ** 2 + (A[2] - B[2]) ** 2)

def MakeAddress(Size, X, Y, R, G, B, *_):
    return "{Address}:{S:01x}{XXX:03x}:{YYYY:04x}:{RR:02x}:{GG:02x}{BB:02x}".format(
        Address=c_RootAddress,
        S=Size,
        XXX=X, YYYY=Y,
        RR=round(R), GG=round(G), BB=round(B)
    )

def ICMPWorkerLogic():
    global g_SharedData
    try:
        SocketObject = socket.socket(socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_ICMPV6)
        SocketObject.setblocking(False)
        SocketObject.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, c_BufferSize * (1024 * 1024))
        SocketObject.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, 0)
        while g_SharedData["Run"]:
            WriteQueue = g_SharedData["WriteQueue"]
            Packet = ICMPv6.MakeEchoPacket(random.randint(0x0000, 0xFFFF), random.randint(0x0000, 0xFFFF), b"")
            for i in range(c_ChunkSize):
                if i >= len(WriteQueue):
                    break
                CurrentTarget = None
                if c_DrawMode == "SCATTER":
                    CurrentTarget = WriteQueue.pop(random.randint(0, len(WriteQueue) - 1))
                elif c_DrawMode == "LAST" or c_DrawMode == "CLOSEST":
                    CurrentTarget = WriteQueue.pop(len(WriteQueue) - 1)
                elif c_DrawMode == "FIRST":
                    CurrentTarget = WriteQueue.pop(0)
                
                SocketObject.sendto(Packet, (MakeAddress(*CurrentTarget), 0))

            time.sleep(c_WaitTime)
            if len(WriteQueue) <= 0:
                LinePrint("*QUEUE EMPTY*")

        SocketObject.close()
    except BaseException as Error:
        print(Error)
    finally:
        g_SharedData["Run"] = False


def main():
    global g_SharedData
    CanvasSize = g_SharedData["CanvasSize"]

    ICMPWorkerThread = threading.Thread(target=ICMPWorkerLogic)
    ICMPWorkerThread.start()

    OriginalTargetImage = Image.open(c_TargetImage)
    TargetImage = OriginalTargetImage.resize((CanvasSize[0], CanvasSize[1]))
    try:
        while g_SharedData["Run"]:
            IterationStart = time.time()

            try:
                CanvasResult = requests.get(c_CanvasURL)
            finally:
                pass

            if not CanvasResult:
                print("Failed To Acquire Canvas Image(Exception).")
            elif CanvasResult.status_code != 200:
                print(f"Failed To Acquire Canvas Image. Status Code {CanvasResult.status_code}")
                time.sleep(3)
                continue
            CanvasImage = Image.open(io.BytesIO(CanvasResult.content))

            # Compare Canvas Image With Target Image
            if CanvasImage.size != TargetImage.size:
                print(f"Canvas/Target Size Mismatch, Canvas: {CanvasImage.size} Target: {TargetImage.size}. Resizing...")
                CanvasSize = CanvasImage.size
                TargetImage = OriginalTargetImage.resize((CanvasSize[0], CanvasSize[1]))

            NewQueue = []
            CPXS = CanvasImage.load() # Canvas Pixels
            TPXS = TargetImage.load() # Target Pixels
            DoneList = []
            for X in range(CanvasSize[0]):
                for Y in range(CanvasSize[1]):
                    CPX = CPXS[X, Y]
                    TPX = TPXS[X, Y]
                    DIFF00 = CompareColor(TPX, CPX)
                    if not (DIFF00 < c_MaxColorDifference) and (not [X, Y] in DoneList):
                        DoneList.append([X + 0, Y + 0])
                        # Can Fit X/Y/All
                        CFX = (X + 1 < CanvasSize[0])
                        CFY = (Y + 1 < CanvasSize[1])
                        CFA = CFX and CFY

                        DIFF10 = (CFX and CompareColor(TPX, TPXS[X + 1, Y + 0])) or 0
                        DIFF01 = (CFY and CompareColor(TPX, TPXS[X + 0, Y + 1])) or 0
                        DIFF11 = (CFA and CompareColor(TPX, TPXS[X + 1, Y + 1])) or 0

                        if CFA and ((DIFF01 + DIFF10 + DIFF11) < (c_MaxColorDifference * 3)):
                            NewQueue.append([2, X, Y, TPX[0], TPX[1], TPX[2], (DIFF00 + DIFF01 + DIFF10 + DIFF11) / 4])
                            DoneList.append([X + 1, Y + 0])
                            DoneList.append([X + 0, Y + 1])
                            DoneList.append([X + 1, Y + 1])
                        else:
                            NewQueue.append([1, X, Y, TPX[0], TPX[1], TPX[2], DIFF00])
                if X % 2 == 0:
                    DoneList.clear()

            if c_DrawMode == "CLOSEST":
                NewQueue.sort(key=lambda v: v[6])
            elif c_DrawMode != "SCATTER":
                NewQueue.sort(key=lambda v: v[0])

            g_SharedData["WriteQueue"] = NewQueue
            LinePrint("Iteration Finished(Took {:.2f} Seconds), {} Canvas Operations Are Required".format(time.time() - IterationStart, len(g_SharedData["WriteQueue"])))
            if len(g_SharedData["WriteQueue"]) == 0:
                time.sleep(2)
    except BaseException as Error:
        print(Error)

    print("Stopping Worker Thread...")
    g_SharedData["Run"] = False
    ICMPWorkerThread.join()




if __name__ == "__main__":
    main()