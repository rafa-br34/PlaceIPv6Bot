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

c_WaitTime = 0 # Time to yield for each iteration
c_ChunkSize = 50 # The amount of pings to ping per iteration
c_RootAddress = "2a01:4f8:c012:f8e6" # Canvas base address
c_CanvasURL = "https://ssi.place/canvas.png" # Canvas base URL
c_TargetImage = "image.png" # Target image
c_MaxColorDifference = 4 # The maximum color difference(Used in every comparison). Recommended: 4, 8, or 16
c_DrawMode = "CLOSEST" # In what order pixels will be drawn [CLOSEST, SCATTER, FIRST, LAST]
c_BufferSize = 16 # Socket buffer size(in MB)
c_SocketCount = 8 # Amount of ICMPv6 sockets to use
c_SocketMode = "DISPERSE" # How to use the ICMPv6 sockets [FOCUS, DISPERSE]
c_ThreadCount = 1 # Amount of worker threads. Recommended: 1
c_ImageCheckWaitTime = 2 # The amount of time to wait before checking the image again if there are no more operations

g_SharedData = {
    "Run": True,
    "WriteQueue": [],
    "CanvasSize": [512, 512],
    "ThreadList": []
}

def LinePrint(*args, sep=' ', end=''):
    ResultString = ""
    for Argument in args:
        ResultString += str(Argument) + sep
    
    PadLen = (os.get_terminal_size()[0] - len(ResultString)) - 1
    Padding = (PadLen > 0 and (' ' * PadLen)) or ''
    print(ResultString, end=Padding + '\r' + end)

g_ProfilerStack = []

def PROFILER_START():
    g_ProfilerStack.append(time.time())
def PROFILER_END():
    return time.time() - g_ProfilerStack.pop()


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
        Sockets = []
        for _ in range(c_SocketCount):
            SocketObject = socket.socket(socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_ICMPV6)
            SocketObject.setblocking(False)
            SocketObject.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, c_BufferSize * (1024 * 1024))
            SocketObject.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, 0)
            Sockets.append(SocketObject)

        SocketIndex = 0
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
                
                Address = (MakeAddress(*CurrentTarget), random.randint(0x0000, 0xFFFF))
                if c_SocketMode == "FOCUS":
                    for SocketObject in Sockets:
                        SocketObject.sendto(Packet, Address)
                elif c_SocketMode == "DISPERSE":
                    if SocketIndex >= len(Sockets):
                        SocketIndex = 0

                    Sockets[SocketIndex].sendto(Packet, Address)

                SocketIndex += 1
            
            if c_WaitTime > 0:
                time.sleep(c_WaitTime)

            if len(WriteQueue) <= 0:
                LinePrint("*QUEUE EMPTY*")
                while len(WriteQueue) <= 0 and g_SharedData["Run"]:
                    time.sleep(c_WaitTime)
                    WriteQueue = g_SharedData["WriteQueue"]
        
        for SocketObject in Sockets:
            SocketObject.close()
    except BaseException as Error:
        print("ICMPWorkerThread Exception:")
        print(Error)
    finally:
        g_SharedData["Run"] = False

def main():
    global g_SharedData
    CanvasSize = g_SharedData["CanvasSize"]
    ThreadList = g_SharedData["ThreadList"]

    for _ in range(c_ThreadCount):
        ICMPWorkerThread = threading.Thread(target=ICMPWorkerLogic)
        ICMPWorkerThread.start()
        ThreadList.append(ICMPWorkerThread)

    PROFILER_START()
    OriginalTargetImage = Image.open(c_TargetImage)
    TargetImage = OriginalTargetImage.resize((CanvasSize[0], CanvasSize[1]))
    LinePrint(f"Loaded & Resized Image In {round(PROFILER_END() * 1000)}ms", end='\n')

    try:
        while g_SharedData["Run"]:
            PROFILER_START()
            try:
                CanvasResult = requests.get(c_CanvasURL)
            except KeyboardInterrupt as KBD:
                raise KBD # Pass To Main Loop
            except (BaseException, ConnectionError, ConnectionResetError) as Error:
                print("Failed To Acquire Canvas Image, Exception:", Error)
                continue
            except:
                print("Failed To Acquire Canvas Image, Unknown Exception")
                continue
            finally:
                pass
                
            if CanvasResult.status_code != 200:
                print(f"Failed To Acquire Canvas Image. Status Code {CanvasResult.status_code}")
                time.sleep(3)
                continue

            CanvasImage = Image.open(io.BytesIO(CanvasResult.content))
            TimeImageAcquire = PROFILER_END()

            # Compare Canvas Image With Target Image
            if CanvasImage.size != TargetImage.size:
                print(f"Canvas/Target Size Mismatch, Canvas: {CanvasImage.size} Target: {TargetImage.size}. Resizing...")
                PROFILER_START()
                CanvasSize = CanvasImage.size
                TargetImage = OriginalTargetImage.resize((CanvasSize[0], CanvasSize[1]))
                print(f"Resized Image In {round(PROFILER_END() * 1000)}ms")

            
            PROFILER_START()
            NewQueue = []
            CPXS = CanvasImage.load() # Canvas Pixels
            TPXS = TargetImage.load() # Target Pixels
            DoneList = []

            def FLAG(X, Y):
                return ((Y & 0xFFFFFF) << 24) | ((X & 0xFFFFFF) << 0)

            for X in range(CanvasSize[0]):
                for Y in range(CanvasSize[1]):
                    CPX = CPXS[X, Y]
                    TPX = TPXS[X, Y]
                    DIFF00 = CompareColor(TPX, CPX)
                    if not (DIFF00 < c_MaxColorDifference) and (not FLAG(X, Y) in DoneList):
                        DoneList.append(FLAG(X + 0, Y + 0))
                        # Can Fit X/Y/All
                        CFX = (X + 1 < CanvasSize[0])
                        CFY = (Y + 1 < CanvasSize[1])
                        CFA = CFX and CFY

                        DIFF10 = (CFX and CompareColor(TPX, TPXS[X + 1, Y + 0])) or 0
                        DIFF01 = (CFY and CompareColor(TPX, TPXS[X + 0, Y + 1])) or 0
                        DIFF11 = (CFA and CompareColor(TPX, TPXS[X + 1, Y + 1])) or 0

                        if CFA and ((DIFF01 + DIFF10 + DIFF11) < (c_MaxColorDifference * 3)):
                            NewQueue.append([2, X, Y, TPX[0], TPX[1], TPX[2], (DIFF00 + DIFF01 + DIFF10 + DIFF11) / 4])
                            DoneList += [FLAG(X + 1, Y + 0), FLAG(X + 0, Y + 1), FLAG(X + 1, Y + 1)]
                        else:
                            NewQueue.append([1, X, Y, TPX[0], TPX[1], TPX[2], DIFF00])
                if X % 2 == 0:
                    DoneList.clear()

            if c_DrawMode == "CLOSEST":
                NewQueue.sort(key=lambda v: v[6])
            elif c_DrawMode != "SCATTER":
                NewQueue.sort(key=lambda v: v[0])

            g_SharedData["WriteQueue"] = NewQueue
            TimeImageProcess = PROFILER_END()
            LinePrint("Image(Acquired In {:.2f}s, Processed In {:.2f}s, {:.2f} Total), {} Draw Operations".format(TimeImageAcquire, TimeImageProcess, TimeImageAcquire + TimeImageProcess, len(g_SharedData["WriteQueue"])))

            if len(g_SharedData["WriteQueue"]) == 0:
                time.sleep(c_ImageCheckWaitTime)
    except KeyboardInterrupt:
        LinePrint("\nKeyboardInterrupt, Stopping...")
    except BaseException as Error:
        LinePrint("\nMain Thread Exception:", end='\n')
        print(Error)

    LinePrint("\nStopping Workers...")
    g_SharedData["Run"] = False
    while len(ThreadList):
        ThreadList.pop().join()




if __name__ == "__main__":
    main()